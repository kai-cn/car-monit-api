package com.ruoyi.base.service.impl;

import com.alibaba.fastjson2.JSON;
import com.alibaba.fastjson2.JSONArray;
import com.alibaba.fastjson2.JSONObject;
import com.ruoyi.base.domain.*;
import com.ruoyi.common.utils.CommonUtil;
import com.ruoyi.common.utils.DateUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.Cursor;
import org.springframework.data.redis.core.RedisCallback;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.data.redis.core.ScanOptions;
import org.springframework.stereotype.Service;

import java.io.IOException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * 多源数据流转服务
 *
 * 功能说明：
 * 1. 统一接收门架抓拍、省界称重、收费站、服务区等多源数据
 * 2. 实现数据标准化转换
 * 3. 按车牌分组进行轨迹拼接
 * 4. 维护待处理队列，处理乱序数据
 * 5. 支持实时轨迹Redis缓存和历史轨迹GaussDB持久化
 */
@Slf4j
@Service
public class MultiSourceDataFlowService {

    @Autowired
    private RedisTemplate redisTemplate;

    // ==================== 常量定义 ====================

    /**
     * Redis中实时轨迹的Key前缀
     */
    private static final String REALTIME_TRAIL_KEY_PREFIX = "trail:realtime:";

    /**
     * Redis中待处理队列的Key前缀
     */
    private static final String PENDING_QUEUE_KEY_PREFIX = "trail:pending:";

    /**
     * 实时轨迹TTL（7天，单位：秒）
     */
    private static final long REALTIME_TRAIL_TTL = 604800;

    /**
     * 轨迹切割时间阈值（7天，单位：毫秒）
     */
    private static final long TRAIL_SPLIT_THRESHOLD = 7 * 24 * 60 * 60 * 1000L;

    /**
     * 待处理队列重试间隔（60秒）
     */
    private static final int PENDING_RETRY_INTERVAL = 60;

    /**
     * 轨迹拼接分段锁数量：同一车牌的读-改-写必须串行，不同车牌按哈希分散
     */
    private static final int PLATE_LOCK_STRIPES = 64;

    private final Object[] plateLocks = new Object[PLATE_LOCK_STRIPES];

    {
        for (int i = 0; i < PLATE_LOCK_STRIPES; i++) {
            plateLocks[i] = new Object();
        }
    }

    /**
     * 取车牌对应的分段锁
     */
    private Object lockForPlate(String plateKey) {
        return plateLocks[(plateKey.hashCode() & 0x7fffffff) % PLATE_LOCK_STRIPES];
    }

    // ==================== 核心处理流程 ====================

    /**
     * 处理多源数据入口方法
     *
     * 思路：统一接收不同来源的数据，转换为标准化TrailBo
     * 目的：屏蔽不同数据源的差异，提供统一的处理接口
     *
     * @param data 原始数据对象
     * @param dataType 数据类型：GantryCapture/BorderWeighingCapture/StationCapture等
     */
    public void processData(Object data, String dataType) {
        log.debug("[数据流转] 收到数据，类型：{}，数据：{}", dataType, data);

        try {
            // 步骤1：将不同来源的数据转换为标准化TrailBo
            TrailBo standardEvent = convertToStandardEvent(data, dataType);
            if (standardEvent == null) {
                log.warn("[数据流转] 数据转换失败，跳过：dataType={}", dataType);
                return;
            }

            // 步骤2：获取车牌标识
            String plateKey = standardEvent.getPlatenumber();
            if (CommonUtil.isBlank(plateKey)) {
                log.warn("[数据流转] 车牌号为空，跳过处理：pointUuid={}", standardEvent.getPointUuid());
                return;
            }

            // 步骤3：尝试直接拼接到轨迹
            boolean appended = tryAppendToTrail(plateKey, standardEvent);

            // 步骤4：如果无法直接拼接，加入待处理队列
            if (!appended) {
                log.info("[数据流转] 无法直接拼接，加入待处理队列：plateKey={}, pointUuid={}",
                        plateKey, standardEvent.getPointUuid());
                addToPendingQueue(plateKey, standardEvent);
            }

        } catch (Exception e) {
            log.error("[数据流转] 处理异常：dataType={}", dataType, e);
        }
    }

    /**
     * 将不同来源的数据转换为标准化TrailBo
     *
     * 思路：根据stateType判断数据来源，调用对应的转换方法
     * 目的：统一多源数据格式，为后续轨迹拼接提供标准化输入
     *
     * @param data 原始数据对象
     * @param dataType 数据类型
     * @return 标准化的TrailBo对象
     */
    private TrailBo convertToStandardEvent(Object data, String dataType) {
        TrailBo trailBo = new TrailBo();
        trailBo.setStateType(dataType);

        switch (dataType) {
            case "GantryCapture":
                // 门架抓拍数据转换
                return convertFromGantryCapture((OdsRtSzdnSnapshotFlowAddcode) data, trailBo);

            case "BorderWeighingCapture":
                // 省界称重数据转换
                return convertFromBorderWeighing(
                        (OdsSzdnProvinceBorderVehicleWeightNewstructure) data, trailBo);

            case "StationCapture":
                // 收费站抓拍数据转换
                return convertFromStationCapture(
                        (OdsRtSzdnSnapshotFlowStationcaptureAddcode) data, trailBo);

            case "FeeRecord":
                // 卡口流水数据转换
                return convertFromFeeRecord((OdsLwzxsfsjFeeRecords01) data, trailBo);

            case "FeeStationEnter":
                // 收费站入口数据转换
                return convertFromFeeStationEnter((OdsLwzxsfsjFeeStationEnter01) data, trailBo);

            case "FeeStationExit":
                // 收费站出口数据转换
                return convertFromFeeStationExit((OdsLwzxsfsjFeeStationExit01) data, trailBo);

            default:
                log.warn("[数据转换] 未知的数据类型：{}", dataType);
                return null;
        }
    }

    /**
     * 门架抓拍数据转换
     */
    private TrailBo convertFromGantryCapture(OdsRtSzdnSnapshotFlowAddcode data, TrailBo trailBo) {
        trailBo.setPointUuid(data.getBigId());
        trailBo.setPlatenumber(data.getPlatenumber());
        trailBo.setCaptureTime(DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, data.getSnapshottime()));
        trailBo.setLocationCode(data.getDeviceip());
        trailBo.setRoadCode(data.getRoadcode());
        trailBo.setSectionCode(data.getSectioncode());
        trailBo.setLon(data.getLon());
        trailBo.setLat(data.getLat());
        trailBo.setGantryCaptureBO(data);
        trailBo.setIpType("gantryip");

        // 补充点UUID到原始数据中
        trailBo.setPointJosn(JSON.toJSONString(data));
        return trailBo;
    }

    /**
     * 省界称重数据转换
     */
    private TrailBo convertFromBorderWeighing(
            OdsSzdnProvinceBorderVehicleWeightNewstructure data, TrailBo trailBo) {
        trailBo.setPointUuid(data.getDatauuid());
        trailBo.setPlatenumber(data.getPlateNo());
        trailBo.setCaptureTime(DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, data.getCheckTime()));
        trailBo.setLocationCode(data.getLocation());
        trailBo.setBorderWeighingCaptureBO(data);
        trailBo.setPointJosn(JSON.toJSONString(data));
        return trailBo;
    }

    /**
     * 收费站抓拍数据转换
     */
    private TrailBo convertFromStationCapture(
            OdsRtSzdnSnapshotFlowStationcaptureAddcode data, TrailBo trailBo) {
        trailBo.setPointUuid(String.valueOf(data.getBigId()));
        trailBo.setPlatenumber(data.getPlatenumber());
        trailBo.setCaptureTime(DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, data.getSnapshottime()));
        trailBo.setLocationCode(data.getDeviceip());
        trailBo.setStationCapture(data);
        trailBo.setIpType("stationip");
        trailBo.setPointJosn(JSON.toJSONString(data));
        return trailBo;
    }

    /**
     * 卡口流水数据转换
     */
    private TrailBo convertFromFeeRecord(OdsLwzxsfsjFeeRecords01 data, TrailBo trailBo) {
        trailBo.setPointUuid(data.getBigId());
        trailBo.setPlatenumber(data.getVehicleplate());
        trailBo.setCaptureTime(DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, data.getTranstime()));
        trailBo.setFeeRecord(data);
        trailBo.setPointJosn(JSON.toJSONString(data));
        return trailBo;
    }

    /**
     * 收费站入口数据转换
     */
    private TrailBo convertFromFeeStationEnter(OdsLwzxsfsjFeeStationEnter01 data, TrailBo trailBo) {
        trailBo.setPointUuid(String.valueOf(data.getBigId()));
        trailBo.setPlatenumber(data.getVehicleid());
        trailBo.setCaptureTime(DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, data.getEntime()));
        trailBo.setLocationCode(data.getEntolllaneid());
        trailBo.setDirectionIn(true); // 标记为进入方向
        trailBo.setFeeStationEnter(data);
        trailBo.setPointJosn(JSON.toJSONString(data));
        return trailBo;
    }

    /**
     * 收费站出口数据转换
     */
    private TrailBo convertFromFeeStationExit(OdsLwzxsfsjFeeStationExit01 data, TrailBo trailBo) {
        trailBo.setPointUuid(data.getBigId());
        trailBo.setPlatenumber(data.getExvehicleid());
        trailBo.setCaptureTime(DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, data.getExtime()));
        trailBo.setLocationCode(data.getExtolllaneid());
        trailBo.setDirectionIn(false); // 标记为驶出方向
        trailBo.setFeeStationExit(data);
        trailBo.setPointJosn(JSON.toJSONString(data));
        return trailBo;
    }

    /**
     * 尝试将事件拼接到现有轨迹
     *
     * 思路：
     * 1. 从Redis获取该车牌的当前轨迹
     * 2. 判断新事件是否能拼接到当前轨迹
     * 3. 如果时间差超过7天，开启新轨迹链
     * 4. 更新轨迹并保存回Redis
     *
     * 目的：实现轨迹的动态拼接和更新
     *
     * @param plateKey 车牌标识
     * @param newEvent 新事件
     * @return 是否拼接成功
     */
    private boolean tryAppendToTrail(String plateKey, TrailBo newEvent) {
        String trailKey = REALTIME_TRAIL_KEY_PREFIX + plateKey;

        // 抓拍时间缺失或格式非法时无法参与排序，直接跳过并记录，交由调用方进入待处理队列
        if (DateUtils.parseDate(newEvent.getCaptureTime()) == null) {
            log.warn("[轨迹拼接] 抓拍时间缺失或格式非法，跳过：plateKey={}, pointUuid={}, captureTime={}",
                    plateKey, newEvent.getPointUuid(), newEvent.getCaptureTime());
            return false;
        }

        // 同一车牌的读-改-写必须串行，否则并发消息会互相覆盖导致轨迹点丢失
        synchronized (lockForPlate(plateKey)) {
            try {
                // 步骤1：获取当前轨迹
                TrailInfo currentTrail = (TrailInfo) redisTemplate.opsForValue().get(trailKey);

                if (currentTrail == null || currentTrail.getTracks() == null) {
                    // 无现有轨迹，创建新轨迹
                    log.info("[轨迹拼接] 无现有轨迹，创建新轨迹：plateKey={}", plateKey);
                    createNewTrail(plateKey, newEvent);
                    return true;
                }

                // 步骤2：判断是否需要切割轨迹（时间差超过7天）
                boolean needSplit = needSplitTrail(currentTrail, newEvent);

                if (needSplit) {
                    log.info("[轨迹拼接] 时间差超过7天，开启新轨迹链：plateKey={}", plateKey);
                    createNewTrail(plateKey, newEvent);
                    return true;
                }

                // 步骤3：拼接到现有轨迹
                appendToExistingTrail(currentTrail, newEvent);

                // 步骤4：保存更新后的轨迹
                redisTemplate.opsForValue().set(trailKey, currentTrail, REALTIME_TRAIL_TTL, TimeUnit.SECONDS);
                log.debug("[轨迹拼接] 成功拼接到现有轨迹：plateKey={}, pointUuid={}",
                        plateKey, newEvent.getPointUuid());

                return true;

            } catch (Exception e) {
                log.error("[轨迹拼接] 异常：plateKey={}", plateKey, e);
                return false;
            }
        }
    }

    /**
     * 判断是否需要切割轨迹
     *
     * 思路：比较新事件时间与轨迹起止时间的差值
     * 目的：超过7天则认为是新的行程
     *
     * @param currentTrail 当前轨迹
     * @param newEvent 新事件
     * @return 是否需要切割
     */
    private boolean needSplitTrail(TrailInfo currentTrail, TrailBo newEvent) {
        ZdataTrailTracks tracks = currentTrail.getTracks();
        Date eventTime = DateUtils.parseDate(newEvent.getCaptureTime());

        // 解析失败或无起止时间时不做切割判定，避免 NPE；非法时间已在入口处拦截
        if (eventTime == null || tracks.getEnterTime() == null || tracks.getExitTime() == null) {
            return false;
        }

        // 计算与进入时间的差
        long diffWithEnter = Math.abs(eventTime.getTime() - tracks.getEnterTime().getTime());
        // 计算与离开时间的差
        long diffWithExit = Math.abs(eventTime.getTime() - tracks.getExitTime().getTime());

        // 任意一个差值超过7天，就需要切割
        return diffWithEnter > TRAIL_SPLIT_THRESHOLD || diffWithExit > TRAIL_SPLIT_THRESHOLD;
    }

    /**
     * 创建新轨迹
     *
     * 思路：以新事件为起点，创建一条新的轨迹链
     * 目的：处理新行程的轨迹初始化
     */
    private void createNewTrail(String plateKey, TrailBo newEvent) {
        TrailInfo newTrail = new TrailInfo();
        ZdataTrailTracks tracks = new ZdataTrailTracks();

        // 生成轨迹UUID
        tracks.setUuid(UUID.randomUUID().toString().replace("-", ""));
        tracks.setPlateKey(plateKey);
        tracks.setType(0); // 初始标记为不完整轨迹
        tracks.setPointCount(1L);

        // 设置时间
        Date eventTime = DateUtils.parseDate(newEvent.getCaptureTime());
        tracks.setEnterTime(eventTime);
        tracks.setExitTime(eventTime);

        // 初始化轨迹点列表
        List<TrailBo> trailList = new ArrayList<>();
        trailList.add(newEvent);

        // 保存完整JSON
        tracks.setTrailPoints(JSON.toJSONString(trailList));

        newTrail.setTrailUuid(tracks.getUuid());
        newTrail.setTracks(tracks);
        newTrail.setTrailList(trailList);

        // 保存到Redis
        String trailKey = REALTIME_TRAIL_KEY_PREFIX + plateKey;
        redisTemplate.opsForValue().set(trailKey, newTrail, REALTIME_TRAIL_TTL, TimeUnit.SECONDS);

        log.info("[轨迹拼接] 创建新轨迹成功：plateKey={}, trailUuid={}", plateKey, tracks.getUuid());
    }

    /**
     * 拼接到现有轨迹
     *
     * 思路：
     * 1. 将新事件加入轨迹点列表
     * 2. 按时间重新排序
     * 3. 更新轨迹的起止时间和点数量
     * 4. 重新生成完整JSON
     *
     * 目的：将新数据整合进现有轨迹，保持轨迹的完整性
     */
    private void appendToExistingTrail(TrailInfo currentTrail, TrailBo newEvent) {
        ZdataTrailTracks tracks = currentTrail.getTracks();
        List<TrailBo> trailList = currentTrail.getTrailList();

        if (trailList == null) {
            trailList = new ArrayList<>();
        }

        // 添加新事件
        trailList.add(newEvent);

        // 按抓拍时间排序（空时间排在最前，避免历史脏数据触发 NPE）
        trailList.sort(Comparator.comparing(TrailBo::getCaptureTime,
                Comparator.nullsFirst(Comparator.<String>naturalOrder())));

        // 更新轨迹信息
        tracks.setPointCount((long) trailList.size());

        // 更新起止时间
        Date firstTime = DateUtils.parseDate(trailList.get(0).getCaptureTime());
        Date lastTime = DateUtils.parseDate(trailList.get(trailList.size() - 1).getCaptureTime());

        if (firstTime != null && (tracks.getEnterTime() == null || firstTime.before(tracks.getEnterTime()))) {
            tracks.setEnterTime(firstTime);
        }
        if (lastTime != null && (tracks.getExitTime() == null || lastTime.after(tracks.getExitTime()))) {
            tracks.setExitTime(lastTime);
        }

        // 如果轨迹点数量足够，标记为完整轨迹
        if (trailList.size() >= 3) {
            tracks.setType(1);
        }

        // 更新完整JSON
        tracks.setTrailPoints(JSON.toJSONString(trailList));

        currentTrail.setTrailList(trailList);
    }

    /**
     * 将事件加入待处理队列
     *
     * 思路：使用Redis List存储待处理事件
     * 目的：暂存无法直接拼接的乱序数据，等待后续重处理
     */
    private void addToPendingQueue(String plateKey, TrailBo event) {
        String queueKey = PENDING_QUEUE_KEY_PREFIX + plateKey;

        // 封装成待处理对象，记录重试次数
        PendingEvent pendingEvent = new PendingEvent();
        pendingEvent.setEvent(event);
        pendingEvent.setRetryCount(0);
        pendingEvent.setCreateTime(new Date());

        // 加入Redis List
        redisTemplate.opsForList().rightPush(queueKey, pendingEvent);

        log.debug("[待处理队列] 加入队列：plateKey={}, pointUuid={}",
                plateKey, event.getPointUuid());
    }

    /**
     * 处理待处理队列（定时任务调用）
     *
     * 思路：定期从队列取出数据重试处理
     * 目的：解决乱序数据问题，保障轨迹完整性
     */
    public void processPendingQueue() {
        log.info("[待处理队列] 开始处理");

        // 使用 SCAN 游标代替 KEYS，避免大 key 空间下阻塞 Redis
        Set<String> keys = scanKeys(PENDING_QUEUE_KEY_PREFIX + "*");

        if (keys == null || keys.isEmpty()) {
            log.info("[待处理队列] 无待处理数据");
            return;
        }

        int totalProcessed = 0;

        for (String queueKey : keys) {
            String plateKey = queueKey.substring(PENDING_QUEUE_KEY_PREFIX.length());

            // 记录本次运行处理的原始元素个数：失败项重新入队后不会被本轮再次取出，避免死循环
            Long queueSize = redisTemplate.opsForList().size(queueKey);
            long batchSize = queueSize == null ? 0 : queueSize;

            for (long i = 0; i < batchSize; i++) {
                // 逐条弹出：处理中途异常时仅丢失当前一条，不会丢掉整批
                Object obj = redisTemplate.opsForList().leftPop(queueKey);

                if (!(obj instanceof PendingEvent)) {
                    if (obj != null) {
                        log.warn("[待处理队列] 非法元素，丢弃：plateKey={}, type={}", plateKey, obj.getClass());
                    }
                    continue;
                }

                PendingEvent pendingEvent = (PendingEvent) obj;

                // 尝试处理
                boolean success = tryAppendToTrail(plateKey, pendingEvent.getEvent());

                if (success) {
                    totalProcessed++;
                } else {
                    // 处理失败，检查重试次数
                    pendingEvent.setRetryCount(pendingEvent.getRetryCount() + 1);

                    if (pendingEvent.getRetryCount() < 3) {
                        // 重新加入队列
                        redisTemplate.opsForList().rightPush(queueKey, pendingEvent);
                    } else {
                        log.warn("[待处理队列] 超过最大重试次数，放弃：plateKey={}, pointUuid={}",
                                plateKey, pendingEvent.getEvent() == null ? null : pendingEvent.getEvent().getPointUuid());
                    }
                }
            }
        }

        log.info("[待处理队列] 处理完成，成功数：{}", totalProcessed);
    }

    /**
     * 使用 SCAN 游标匹配 key，返回集合与 KEYS 相同（非阻塞）
     */
    private Set<String> scanKeys(String pattern) {
        Set<String> keys = new LinkedHashSet<>();
        redisTemplate.execute((RedisCallback<Void>) connection -> {
            Cursor<byte[]> cursor = connection.scan(
                    ScanOptions.scanOptions().match(pattern).count(1000).build());
            try {
                cursor.forEachRemaining(bytes -> keys.add(new String(bytes, StandardCharsets.UTF_8)));
            } finally {
                try {
                    cursor.close();
                } catch (IOException e) {
                    log.warn("[待处理队列] 关闭 SCAN 游标异常", e);
                }
            }
            return null;
        });
        return keys;
    }

    /**
     * 待处理事件包装类
     */
    @lombok.Data
    private static class PendingEvent {
        private TrailBo event;
        private int retryCount;
        private Date createTime;
    }
}
