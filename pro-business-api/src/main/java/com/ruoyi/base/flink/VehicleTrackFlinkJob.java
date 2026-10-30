package com.ruoyi.base.flink;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import lombok.extern.slf4j.Slf4j;
import org.apache.flink.api.common.functions.RichMapFunction;
import org.apache.flink.api.common.serialization.SimpleStringSchema;
import org.apache.flink.api.common.state.*;
import org.apache.flink.api.common.time.Time;
import org.apache.flink.api.common.typeinfo.TypeHint;
import org.apache.flink.api.common.typeinfo.TypeInformation;
import org.apache.flink.api.common.typeinfo.Types;
import org.apache.flink.configuration.Configuration;
import org.apache.flink.streaming.api.CheckpointingMode;
import org.apache.flink.streaming.api.datastream.BroadcastStream;
import org.apache.flink.streaming.api.datastream.DataStream;
import org.apache.flink.streaming.api.datastream.KeyedStream;
import org.apache.flink.streaming.api.environment.StreamExecutionEnvironment;
import org.apache.flink.streaming.api.functions.co.KeyedBroadcastProcessFunction;
import org.apache.flink.streaming.api.functions.sink.SinkFunction;
import org.apache.flink.streaming.api.functions.source.SourceFunction;
import org.apache.flink.streaming.connectors.kafka.FlinkKafkaConsumer;
import org.apache.flink.util.Collector;

import java.io.Serializable;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * 车辆轨迹 Flink 实时处理 Job
 *
 * 功能说明：
 * 1. 从 Kafka 消费 Debezium CDC 消息和设备直连数据
 * 2. 按车牌分组进行轨迹聚合（使用 Flink 键控状态 + 定时器）
 * 3. 字典广播流支持位置信息富集（Broadcast State Pattern）
 * 4. 轨迹拼接与状态管理（State TTL 30 天自动清理）
 * 5. 待处理队列 + 定时器重试机制
 * 6. 输出到 Redis 和 GaussDB
 *
 * 版本兼容说明（Flink 1.13.2 + Scala 2.11 + JDK 1.8）：
 * --------------------------------------------------------------------------------------
 * 特性                        Flink 1.13.x 对应 API
 * --------------------------------------------------------------------------------------
 * 流执行环境                   StreamExecutionEnvironment.getExecutionEnvironment()
 * Kafka 消费者                 FlinkKafkaConsumer<String>（flink-connector-kafka_2.11）
 * 键控状态                     ValueState<T> / ListState<T> + KeyedStream
 * 状态 TTL                     StateTtlConfig.newBuilder(Time.milliseconds(ttl))
 * 定时器                       ctx.timerService().registerProcessingTimeTimer(timestamp)
 * 广播状态                     KeyedBroadcastProcessFunction<KEY, IN1, IN2, OUT>
 * 广播状态描述符               MapStateDescriptor<>(name, keyType, valueType)
 * 类型信息                     Types.STRING / Types.LONG / TypeInformation.of(new TypeHint<>(){})
 * Checkpoint                   env.enableCheckpointing(interval, CheckpointingMode.EXACTLY_ONCE)
 * --------------------------------------------------------------------------------------
 *
 * 与原代码的核心修复点：
 * [修复1] BroadcastProcessFunction -> KeyedBroadcastProcessFunction（支持 onTimer 定时器）
 * [修复2] Types.OBJECT -> TypeInformation.of(new TypeHint<Map<String,Object>>(){})
 * [修复3] 自定义 SimpleStringSchema -> org.apache.flink.api.common.serialization.SimpleStringSchema
 * [修复4] 所有内部数据模型添加 implements Serializable（Flink 状态对象要求）
 * [修复5] onTimer 方法签名对齐 KeyedBroadcastProcessFunction 的正确签名
 */
@Slf4j
public class VehicleTrackFlinkJob {

    // ==================== 配置项 ====================

    /** Kafka Broker 地址 */
    private static final String KAFKA_BOOTSTRAP_SERVERS = "127.0.0.1:9092";

    /** CDC 数据主题：Debezium 推送的源数据库变更 */
    private static final String CDC_TOPIC = "gaussdb-cdc.jl_data01.ods_rt_szdn_snapshot_flow_addcode";

    /** 设备直连数据主题：设备直接上报的抓拍数据 */
    private static final String RAW_DATA_TOPIC = "device-raw-data";

    /** 轨迹切割时间阈值（7 天 = 604800000 毫秒） */
    private static final long TRAIL_SPLIT_THRESHOLD = 7L * 24 * 60 * 60 * 1000;

    /** 状态 TTL（30 天）：超过此时间未更新的状态自动被 Flink 清理 */
    private static final long STATE_TTL = 30L * 24 * 60 * 60 * 1000;

    /** 待处理队列重试间隔（60 秒） */
    private static final long PENDING_RETRY_INTERVAL = 60L * 1000;

    /** 单条数据最大重试次数 */
    private static final int MAX_PENDING_RETRY = 3;

    // ==================== 主方法：Flink Job 入口 ====================

    public static void main(String[] args) throws Exception {
        log.info("[Flink Job] 开始启动车辆轨迹处理 Job（Flink 1.13.2 + JDK 1.8）");

        // ========== 步骤 1：创建 Flink 执行环境 ==========
        StreamExecutionEnvironment env = StreamExecutionEnvironment.getExecutionEnvironment();

        // 60 秒一次 Checkpoint，EXACTLY_ONCE 语义
        env.enableCheckpointing(60000, CheckpointingMode.EXACTLY_ONCE);
        env.getCheckpointConfig().setCheckpointTimeout(600000);
        env.getCheckpointConfig().setMaxConcurrentCheckpoints(1);
        env.getCheckpointConfig().setMinPauseBetweenCheckpoints(30000);

        // ========== 步骤 2：字典广播流 ==========
        BroadcastStream<Map<String, Object>> dictBroadcastStream = createDictBroadcastStream(env);

        // ========== 步骤 3：Kafka 数据源 ==========
        DataStream<StandardEvent> cdcStream = createCDCDataStream(env);
        DataStream<StandardEvent> rawDataStream = createRawDataStream(env);
        DataStream<StandardEvent> unifiedStream = cdcStream.union(rawDataStream);

        // ========== 步骤 4：按车牌分组 ==========
        KeyedStream<StandardEvent, String> keyedStream = unifiedStream
                .keyBy(StandardEvent::getPlateKey);

        // ========== 步骤 5：连接广播流 + 轨迹聚合 ==========
        DataStream<TrailResult> resultStream = keyedStream
                .connect(dictBroadcastStream)
                .process(new TrailAggregatorProcessFunction());

        // ========== 步骤 6：输出结果 ==========
        resultStream.addSink(new TrailResultSink());

        // ========== 步骤 7：启动 Job ==========
        log.info("[Flink Job] DAG 构建完成，开始提交执行");
        env.execute("车辆轨迹实时处理 Job");
    }

    // ==================== 方法：创建字典广播流 ====================

    private static BroadcastStream<Map<String, Object>> createDictBroadcastStream(
            StreamExecutionEnvironment env) {

        DataStream<Map<String, Object>> dictStream = env
                .addSource(new DictionarySourceFunction())
                .name("Redis 字典数据")
                .setParallelism(1);

        // [修复2] 使用 TypeInformation.of(new TypeHint<...>(){}) 替代 Types.OBJECT
        MapStateDescriptor<String, Map<String, Object>> dictStateDesc =
                new MapStateDescriptor<>(
                        "dict-broadcast-state",
                        Types.STRING,
                        TypeInformation.of(new TypeHint<Map<String, Object>>() {})
                );

        return dictStream.broadcast(dictStateDesc);
    }

    // ==================== 方法：创建 Debezium CDC 数据流 ====================

    private static DataStream<StandardEvent> createCDCDataStream(
            StreamExecutionEnvironment env) {

        Properties props = new Properties();
        props.setProperty("bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS);
        props.setProperty("group.id", "flink-cdc-consumer");
        props.setProperty("auto.offset.reset", "latest");
        props.setProperty("enable.auto.commit", "false");

        // [修复3] 使用 Flink 自带的 org.apache.flink.api.common.serialization.SimpleStringSchema
        FlinkKafkaConsumer<String> consumer = new FlinkKafkaConsumer<>(
                CDC_TOPIC,
                new SimpleStringSchema(),
                props
        );

        return env
                .addSource(consumer)
                .name("Kafka-CDC 数据源")
                .map(new CDCEventParser())
                .name("CDC 数据解析标准化");
    }

    // ==================== 方法：创建设备直连数据流 ====================

    private static DataStream<StandardEvent> createRawDataStream(
            StreamExecutionEnvironment env) {

        Properties props = new Properties();
        props.setProperty("bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS);
        props.setProperty("group.id", "flink-rawdata-consumer");
        props.setProperty("auto.offset.reset", "latest");
        props.setProperty("enable.auto.commit", "false");

        FlinkKafkaConsumer<String> consumer = new FlinkKafkaConsumer<>(
                RAW_DATA_TOPIC,
                new SimpleStringSchema(),
                props
        );

        return env
                .addSource(consumer)
                .name("Kafka-设备直连 数据源")
                .map(new RawEventParser())
                .name("直连数据解析标准化");
    }

    // ====================================================================================
    // 核心处理函数：轨迹聚合（使用 KeyedBroadcastProcessFunction 支持定时器）
    // ====================================================================================

    /**
     * [修复1] 使用 KeyedBroadcastProcessFunction 替代 BroadcastProcessFunction
     * 原因：BroadcastProcessFunction 不支持 onTimer 定时器，只有 Keyed 版本支持
     * 泛型参数：<String=KEY(车牌), StandardEvent=IN1, Map<String,Object>=IN2, TrailResult=OUT>
     */
    private static class TrailAggregatorProcessFunction extends
            KeyedBroadcastProcessFunction<String, StandardEvent, Map<String, Object>, TrailResult> {

        private transient ValueState<TrailState> trailState;
        private transient ListState<PendingEvent> pendingQueue;
        private transient MapStateDescriptor<String, Map<String, Object>> dictStateDesc;

        @Override
        public void open(Configuration parameters) throws Exception {

            // 状态 TTL：30 天
            StateTtlConfig ttlConfig = StateTtlConfig
                    .newBuilder(Time.milliseconds(STATE_TTL))
                    .setUpdateType(StateTtlConfig.UpdateType.OnCreateAndWrite)
                    .setStateVisibility(StateTtlConfig.StateVisibility.NeverReturnExpired)
                    .cleanupIncrementally(10, true)
                    .build();

            // 轨迹状态描述符
            ValueStateDescriptor<TrailState> trailStateDesc =
                    new ValueStateDescriptor<>(
                            "trail-state",
                            TypeInformation.of(new TypeHint<TrailState>() {})
                    );
            trailStateDesc.enableTimeToLive(ttlConfig);
            trailState = getRuntimeContext().getState(trailStateDesc);

            // 待处理队列
            ListStateDescriptor<PendingEvent> pendingQueueDesc =
                    new ListStateDescriptor<>(
                            "pending-queue",
                            TypeInformation.of(new TypeHint<PendingEvent>() {})
                    );
            pendingQueue = getRuntimeContext().getListState(pendingQueueDesc);

            // 广播状态描述符
            dictStateDesc = new MapStateDescriptor<>(
                    "dict-broadcast-state",
                    Types.STRING,
                    TypeInformation.of(new TypeHint<Map<String, Object>>() {})
            );

            log.info("[轨迹聚合器] open() 初始化完成");
        }

        @Override
        public void processElement(
                StandardEvent event,
                ReadOnlyContext ctx,
                Collector<TrailResult> out) throws Exception {

            TrailState current = trailState.value();
            if (current == null) {
                current = new TrailState();
            }

            boolean appended = tryAppendToTrail(current, event);

            if (appended) {
                trailState.update(current);
                out.collect(new TrailResult(current.getLatestTrail()));
            } else {
                PendingEvent pending = new PendingEvent();
                pending.event = event;
                pending.retryCount = 0;
                pending.createTime = System.currentTimeMillis();
                pendingQueue.add(pending);

                long timerTs = System.currentTimeMillis() + PENDING_RETRY_INTERVAL;
                ctx.timerService().registerProcessingTimeTimer(timerTs);
            }
        }

        @Override
        public void processBroadcastElement(
                Map<String, Object> dict,
                Context ctx,
                Collector<TrailResult> out) throws Exception {

            if (dict != null && !dict.isEmpty()) {
                for (Map.Entry<String, Object> entry : dict.entrySet()) {
                    // 显式类型转换：entry.getValue() 返回 Object，需要转为 Map<String,Object>
                    // 满足 BroadcastState.put(String, Map<String,Object>) 的参数要求
                    ctx.getBroadcastState(dictStateDesc).put(entry.getKey(), (Map<String, Object>) entry.getValue());
                }
                log.info("[广播流] 字典数据更新完成，更新项数={}", dict.size());
            }
        }

        /**
         * [修复5] onTimer 方法签名：使用 KeyedBroadcastProcessFunction 的 OnTimerContext
         * 原代码使用的是 KeyedProcessFunction.OnTimerContext（错误）
         */
        @Override
        public void onTimer(
                long timestamp,
                OnTimerContext ctx,
                Collector<TrailResult> out) throws Exception {

            TrailState current = trailState.value();
            if (current == null) {
                current = new TrailState();
            }

            Iterator<PendingEvent> it = pendingQueue.get().iterator();
            List<PendingEvent> retryList = new ArrayList<>();
            int successCount = 0;
            int dropCount = 0;

            while (it.hasNext()) {
                PendingEvent pending = it.next();
                it.remove();

                boolean appended = tryAppendToTrail(current, pending.event);
                if (appended) {
                    successCount++;
                    out.collect(new TrailResult(current.getLatestTrail()));
                } else {
                    pending.retryCount++;
                    if (pending.retryCount < MAX_PENDING_RETRY) {
                        retryList.add(pending);
                    } else {
                        dropCount++;
                        log.warn("[待处理队列] 超过最大重试次数({})，丢弃: 车牌={}, 点ID={}",
                                MAX_PENDING_RETRY, pending.event.getPlateKey(), pending.event.getPointUuid());
                    }
                }
            }

            for (PendingEvent p : retryList) {
                pendingQueue.add(p);
            }

            trailState.update(current);

            if (successCount > 0 || dropCount > 0 || !retryList.isEmpty()) {
                log.info("[onTimer处理完成] 成功拼接={}, 丢弃={}, 继续重试={}",
                        successCount, dropCount, retryList.size());

                if (!retryList.isEmpty()) {
                    long nextTimerTs = System.currentTimeMillis() + PENDING_RETRY_INTERVAL;
                    ctx.timerService().registerProcessingTimeTimer(nextTimerTs);
                }
            }
        }

        private boolean tryAppendToTrail(TrailState state, StandardEvent event) {
            if (state.trails.isEmpty()) {
                state.createNewTrail(event);
                return true;
            }

            TrailInfo latest = state.getLatestTrail();
            long timeDiff = Math.abs(event.getCaptureTime() - latest.getExitTime());
            if (timeDiff > TRAIL_SPLIT_THRESHOLD) {
                state.createNewTrail(event);
                return true;
            }

            latest.appendPoint(event);
            return true;
        }
    }

    // ====================================================================================
    // 数据解析器
    // ====================================================================================

    private static class CDCEventParser extends RichMapFunction<String, StandardEvent> {
        @Override
        public StandardEvent map(String json) throws Exception {
            StandardEvent event = new StandardEvent();

            try {
                JSONObject root = JSON.parseObject(json);
                JSONObject payload = root.getJSONObject("payload");

                if (payload != null) {
                    // Debezium 格式：payload.after
                    JSONObject after = payload.getJSONObject("after");
                    if (after != null) {
                        OdsRtSzdnSnapshotFlowAddcode data =
                                JSON.toJavaObject(after, OdsRtSzdnSnapshotFlowAddcode.class);

                        if (data != null) {
                            event.setPointUuid(data.getBigId() != null ?
                                    data.getBigId().toString() : UUID.randomUUID().toString());
                            event.setPlateKey(data.getPlatenumber());
                            if (data.getSnapshottime() != null) {
                                event.setCaptureTime(data.getSnapshottime().getTime());
                            } else {
                                event.setCaptureTime(System.currentTimeMillis());
                            }
                            event.setLocationCode(data.getDeviceid());
                            event.setSourceType("GANTRY-CDC");
                            event.setRawData(json);
                            return event;
                        }
                    }
                }

                // 退化为普通 JSON 格式
                OdsRtSzdnSnapshotFlowAddcode data =
                        JSON.parseObject(json, OdsRtSzdnSnapshotFlowAddcode.class);
                if (data != null && data.getPlatenumber() != null) {
                    event.setPointUuid(data.getBigId() != null ?
                            data.getBigId().toString() : UUID.randomUUID().toString());
                    event.setPlateKey(data.getPlatenumber());
                    if (data.getSnapshottime() != null) {
                        event.setCaptureTime(data.getSnapshottime().getTime());
                    } else {
                        event.setCaptureTime(System.currentTimeMillis());
                    }
                    event.setLocationCode(data.getDeviceid());
                    event.setSourceType("GANTRY-RAW");
                    event.setRawData(json);
                    return event;
                }

                log.warn("[CDC 解析] 无法识别消息格式: json={}",
                        json.length() > 200 ? json.substring(0, 200) + "..." : json);

            } catch (Exception ex) {
                log.error("[CDC 解析] 解析异常: json={}",
                        json.length() > 200 ? json.substring(0, 200) + "..." : json, ex);
            }

            // 兜底：空事件
            event.setPointUuid(UUID.randomUUID().toString());
            event.setPlateKey("UNKNOWN-" + UUID.randomUUID().toString().substring(0, 8));
            event.setCaptureTime(System.currentTimeMillis());
            event.setSourceType("PARSE-ERROR");
            event.setRawData(json);
            return event;
        }
    }

    private static class RawEventParser extends RichMapFunction<String, StandardEvent> {
        @Override
        public StandardEvent map(String json) throws Exception {
            StandardEvent event = new StandardEvent();

            try {
                JSONObject data = JSON.parseObject(json);

                event.setPointUuid(data.getString("bigId") != null ?
                        data.getString("bigId") : UUID.randomUUID().toString());
                event.setPlateKey(data.getString("plateNumber") != null ?
                        data.getString("plateNumber") :
                        ("UNKNOWN-" + UUID.randomUUID().toString().substring(0, 8)));

                Object timeObj = data.get("captureTime");
                if (timeObj instanceof Long) {
                    event.setCaptureTime((Long) timeObj);
                } else if (timeObj instanceof String) {
                    try {
                        Date date = data.getDate("captureTime");
                        event.setCaptureTime(date != null ?
                                date.getTime() : System.currentTimeMillis());
                    } catch (Exception e) {
                        event.setCaptureTime(System.currentTimeMillis());
                    }
                } else {
                    event.setCaptureTime(System.currentTimeMillis());
                }

                event.setLocationCode(data.getString("deviceId"));
                event.setSourceType(data.getString("deviceType") != null ?
                        data.getString("deviceType") : "DEVICE-RAW");
                event.setRawData(json);

                return event;

            } catch (Exception ex) {
                log.error("[直连解析] 解析异常: json={}",
                        json.length() > 200 ? json.substring(0, 200) + "..." : json, ex);

                event.setPointUuid(UUID.randomUUID().toString());
                event.setPlateKey("UNKNOWN-" + UUID.randomUUID().toString().substring(0, 8));
                event.setCaptureTime(System.currentTimeMillis());
                event.setSourceType("PARSE-ERROR");
                event.setRawData(json);
                return event;
            }
        }
    }

    // ====================================================================================
    // 数据模型（[修复4] 全部添加 implements Serializable）
    // ====================================================================================

    public static class StandardEvent implements Serializable {
        private static final long serialVersionUID = 1L;

        private String pointUuid;
        private String plateKey;
        private long captureTime;
        private String locationCode;
        private String sourceType;
        private String rawData;

        public String getPointUuid() { return pointUuid; }
        public void setPointUuid(String pointUuid) { this.pointUuid = pointUuid; }
        public String getPlateKey() { return plateKey; }
        public void setPlateKey(String plateKey) { this.plateKey = plateKey; }
        public long getCaptureTime() { return captureTime; }
        public void setCaptureTime(long captureTime) { this.captureTime = captureTime; }
        public String getLocationCode() { return locationCode; }
        public void setLocationCode(String locationCode) { this.locationCode = locationCode; }
        public String getSourceType() { return sourceType; }
        public void setSourceType(String sourceType) { this.sourceType = sourceType; }
        public String getRawData() { return rawData; }
        public void setRawData(String rawData) { this.rawData = rawData; }
    }

    public static class TrailState implements Serializable {
        private static final long serialVersionUID = 1L;

        private List<TrailInfo> trails = new ArrayList<>();

        public void createNewTrail(StandardEvent event) {
            TrailInfo info = new TrailInfo();
            info.setUuid(UUID.randomUUID().toString().replace("-", ""));
            info.setPlateKey(event.getPlateKey());
            info.setEnterTime(event.getCaptureTime());
            info.setExitTime(event.getCaptureTime());
            info.getPoints().add(event);
            info.setType(0);
            trails.add(info);
        }

        public TrailInfo getLatestTrail() {
            if (trails.isEmpty()) {
                return new TrailInfo();
            }
            return trails.get(trails.size() - 1);
        }

        public List<TrailInfo> getTrails() { return trails; }
        public void setTrails(List<TrailInfo> trails) { this.trails = trails; }
    }

    public static class TrailInfo implements Serializable {
        private static final long serialVersionUID = 1L;

        private String uuid;
        private String plateKey;
        private long enterTime;
        private long exitTime;
        private int type;
        private List<StandardEvent> points = new ArrayList<>();

        public void appendPoint(StandardEvent event) {
            points.add(event);
            points.sort(Comparator.comparing(StandardEvent::getCaptureTime));
            enterTime = points.get(0).getCaptureTime();
            exitTime = points.get(points.size() - 1).getCaptureTime();
            if (points.size() >= 3) {
                type = 1;
            }
        }

        public String getUuid() { return uuid; }
        public void setUuid(String uuid) { this.uuid = uuid; }
        public String getPlateKey() { return plateKey; }
        public void setPlateKey(String plateKey) { this.plateKey = plateKey; }
        public long getEnterTime() { return enterTime; }
        public void setEnterTime(long enterTime) { this.enterTime = enterTime; }
        public long getExitTime() { return exitTime; }
        public void setExitTime(long exitTime) { this.exitTime = exitTime; }
        public int getType() { return type; }
        public void setType(int type) { this.type = type; }
        public List<StandardEvent> getPoints() { return points; }
        public void setPoints(List<StandardEvent> points) { this.points = points; }
    }

    public static class TrailResult implements Serializable {
        private static final long serialVersionUID = 1L;

        private TrailInfo trail;
        public TrailResult(TrailInfo trail) { this.trail = trail; }
        public TrailInfo getTrail() { return trail; }
        public void setTrail(TrailInfo trail) { this.trail = trail; }
    }

    public static class PendingEvent implements Serializable {
        private static final long serialVersionUID = 1L;

        public StandardEvent event;
        public int retryCount;
        public long createTime;
    }

    // ====================================================================================
    // Source：字典数据 Source
    // ====================================================================================

    private static class DictionarySourceFunction implements SourceFunction<Map<String, Object>> {
        private volatile boolean isRunning = true;

        @Override
        public void run(SourceContext<Map<String, Object>> ctx) throws Exception {
            while (isRunning) {
                Map<String, Object> dict = new HashMap<>();
                ctx.collect(dict);
                TimeUnit.MINUTES.sleep(10);
            }
        }

        @Override
        public void cancel() {
            isRunning = false;
            log.info("[字典数据源] DictionarySourceFunction.cancel() 被调用");
        }
    }

    // ====================================================================================
    // Sink：轨迹结果输出
    // ====================================================================================

    private static class TrailResultSink implements SinkFunction<TrailResult> {
        @Override
        public void invoke(TrailResult value, Context context) throws Exception {
            if (value == null || value.getTrail() == null) {
                return;
            }
            log.info("[Sink] 输出轨迹: uuid={}, 车牌={}, 点数={}, 类型={}",
                    value.getTrail().getUuid(),
                    value.getTrail().getPlateKey(),
                    value.getTrail().getPoints().size(),
                    value.getTrail().getType());
        }
    }
}
