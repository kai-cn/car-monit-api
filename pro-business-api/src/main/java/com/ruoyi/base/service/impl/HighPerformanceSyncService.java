package com.ruoyi.base.service.impl;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.*;
import com.ruoyi.base.service.*;
import com.ruoyi.common.constant.Constants;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import com.ruoyi.common.utils.spring.SpringUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.text.ParseException;
import java.text.SimpleDateFormat;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;

/**
 * 高性能同步可疑车辆服务
 * <p>
 * 优化策略：
 * 1. 游标分页替代offset分页（避免大offset性能问题）
 * 2. 多线程并行处理（CPU密集型任务并行化）
 * 3. 批量操作优化（批量查询、批量写入）
 * 4. 数据预处理（提前加载缓存数据）
 * 5. Java 8 Stream API 优化遍历和过滤
 * </p>
 *
 * @author ruoyi
 */
@Slf4j
@Service
public class HighPerformanceSyncService {

    @Autowired
    private RedisCache redisCache;

    @Autowired
    private IZdataTrailTracksService zdataTrailTracksService;

    @Autowired
    private IOdsSzdnGantryService odsSzdnGantryService;

    @Autowired
    private IZdataLocationDictService zdataLocationDictService;

    @Autowired
    private IOdsSzdnSectionService sectionService;

    @Autowired
    private IOdsRtSzdnSnapshotFlowAddcodeService snapshotFlowAddcodeService;

    @Autowired
    private IOdsLwzxsfsjFeeRecords01Service feeRecords01Service;


    @Value("${isLocalhost}")
    private String isLocalhost;

    // 配置常量
    private static final String redisTimeKey = "sys_config:syncSuspiciousCar_time";
    private static final String redisBiteKey = "sys_config:syncSuspiciousCar_bite";
    private static final String supoer_mjnum = "sys_config:supoer_mjnum";
    private static final String road_supoer_mjnum = "sys_config:road_supoer_mjnum";

    // 线程池配置
    private static final int CORE_POOL_SIZE = Runtime.getRuntime().availableProcessors();
    private static final int MAX_POOL_SIZE = CORE_POOL_SIZE * 2;
    private static final int QUEUE_CAPACITY = 1000;
    private static final long KEEP_ALIVE_TIME = 60L;

    /**
     * 高性能线程池
     * - 使用固定大小线程池，适合 I/O 密集型任务
     */
    private final ExecutorService executorService = Executors.newFixedThreadPool(CORE_POOL_SIZE, new ThreadFactory() {
        private final AtomicInteger counter = new AtomicInteger(0);

        @Override
        public Thread newThread(Runnable r) {
            Thread thread = new Thread(r, "sync-suspicious-car-" + counter.incrementAndGet());
            thread.setDaemon(true);
            return thread;
        }
    });

    /**
     * 方法1：多线程 + 游标分页的高性能同步方法
     * <p>
     * 核心优化点：
     * 1. 使用游标分页（基于ID或时间戳）避免offset分页的性能问题
     * 2. 多线程并行处理不同的数据块
     * 3. 批量查询和批量写入
     * 4. 数据预处理和缓存
     * </p>
     *
     * @param startNum 起始页码
     * @param endNum   结束页码
     */
    public void syncSuspiciousCarHighPerformance(int startNum, int endNum) {
        long startTime = System.currentTimeMillis();
        log.info("[高性能同步] 开始执行，页码范围: {}-{}", startNum, endNum);

        // 1. 加载配置和缓存数据（预加载，避免重复查询）
        SyncConfig config = loadSyncConfig();
        PreloadedData preloadedData = preloadData();

        // 2. 计算时间范围
        DateRange dateRange = calculateDateRange(config.starTime, config.endTime);
        log.info("[高性能同步] 时间范围: {} - {}", dateRange.startTime, dateRange.endTime);

        // 3. 使用游标分页查询轨迹数据
        List<ZdataTrailTracks> allTrailTracks = queryTrailTracksWithCursor(dateRange, config.pageSize);
        log.info("[高性能同步] 查询到轨迹数据: {} 条", allTrailTracks.size());

        // 4. 多线程并行处理可疑车辆分析
        List<TrailInfo> suspiciousVehicles = processSuspiciousVehiclesParallel(
                allTrailTracks, preloadedData, config, dateRange.formattedDate);

        // 5. 批量写入Redis
        batchWriteToRedis(suspiciousVehicles, dateRange.formattedDate);

        long duration = System.currentTimeMillis() - startTime;
        log.info("[高性能同步] 完成，耗时: {}ms, 可疑车辆: {} 辆", duration, suspiciousVehicles.size());
    }

    /**
     * 方法2：使用ForkJoinPool的递归并行处理版本
     * <p>
     * 适合超大数据量场景，采用分治策略
     * </p>
     */
    public void syncSuspiciousCarForkJoin(int startNum, int endNum) {
        long startTime = System.currentTimeMillis();
        log.info("[ForkJoin同步] 开始执行");

        SyncConfig config = loadSyncConfig();
        PreloadedData preloadedData = preloadData();
        DateRange dateRange = calculateDateRange(config.starTime, config.endTime);

        // 获取所有轨迹数据
        List<ZdataTrailTracks> allTrailTracks = queryTrailTracksWithCursor(dateRange, config.pageSize);

        // 使用ForkJoinPool进行并行处理
        ForkJoinPool forkJoinPool = new ForkJoinPool(CORE_POOL_SIZE);
        try {
            SuspiciousVehicleTask task = new SuspiciousVehicleTask(
                    allTrailTracks, 0, allTrailTracks.size(), preloadedData, config, dateRange.formattedDate);
            List<TrailInfo> suspiciousVehicles = forkJoinPool.invoke(task);

            // 批量写入Redis
            batchWriteToRedis(suspiciousVehicles, dateRange.formattedDate);

            long duration = System.currentTimeMillis() - startTime;
            log.info("[ForkJoin同步] 完成，耗时: {}ms, 可疑车辆: {} 辆", duration, suspiciousVehicles.size());
        } finally {
            forkJoinPool.shutdown();
        }
    }

    /**
     * 方法3：流式处理 + 管道模式版本
     * <p>
     * 使用Java 8 Stream API实现流式处理，代码更简洁
     * </p>
     */
    public void syncSuspiciousCarStream(int startNum, int endNum) {
        long startTime = System.currentTimeMillis();
        log.info("[流式同步] 开始执行");

        SyncConfig config = loadSyncConfig();
        PreloadedData preloadedData = preloadData();
        DateRange dateRange = calculateDateRange(config.starTime, config.endTime);

        // 流式处理管道
        List<TrailInfo> suspiciousVehicles = queryTrailTracksWithCursor(dateRange, config.pageSize)
                .stream()
                // 1. 过滤：只处理非节假日的跨省车辆
                .filter(track -> filterNonHolidayCrossProvince(track, preloadedData.holidayDates))
                // 2. 转换：解析轨迹点
                .map(track -> parseTrailPoints(track, preloadedData.sectionCodes))
                // 3. 过滤：可疑车辆判断
                .filter(tuple -> isSuspiciousVehicle(tuple, config))
                // 4. 转换：构建TrailInfo
                .map(tuple -> buildTrailInfo(tuple.tracks, tuple.trailBoList, preloadedData))
                // 5. 收集结果
                .collect(Collectors.toList());

        // 批量写入Redis
        batchWriteToRedis(suspiciousVehicles, dateRange.formattedDate);

        long duration = System.currentTimeMillis() - startTime;
        log.info("[流式同步] 完成，耗时: {}ms, 可疑车辆: {} 辆", duration, suspiciousVehicles.size());
    }

    /**
     * 方法4：时间范围分片 + 多线程游标查询（推荐方案）
     * <p>
     * 核心思路：
     * 1. 将大的时间范围按小时/天分片，避免全表扫描
     * 2. 每个分片使用独立线程并行查询
     * 3. 每个分片内部继续使用游标分页优化性能
     * 4. 最后合并所有结果并排序
     * <p>
     * 适用场景：数据量非常大（>100万条），需要极致查询性能
     * </p>
     *
     * @param startNum 起始页码
     * @param endNum   结束页码
     */
    public void syncSuspiciousCarByTimeRange(int startNum, int endNum) {
        long startTime = System.currentTimeMillis();
        log.info("[时间分片同步] 开始执行，页码范围: {}-{}", startNum, endNum);

        // 1. 加载配置和缓存数据（预加载，避免重复查询）
        SyncConfig config = loadSyncConfig();
        PreloadedData preloadedData = preloadData();

        // 2. 计算时间范围
        DateRange dateRange = calculateDateRange(config.starTime, config.endTime);
        log.info("[时间分片同步] 原始时间范围: {} - {}", dateRange.startTime, dateRange.endTime);

        // 3. 时间范围分片（按小时分片，线程数=CPU核心数）
        List<DateRange> subRanges = splitDateRangeByHour(dateRange, CORE_POOL_SIZE);
        log.info("[时间分片同步] 分片数量: {}, 每个分片独立查询", subRanges.size());

        // 4. 多线程并行查询每个时间分片的数据
        List<ZdataTrailTracks> allTrailTracks = queryTrailTracksParallelByRange(subRanges, config.pageSize);
        log.info("[时间分片同步] 总查询轨迹数据: {} 条", allTrailTracks.size());

        // 5. 多线程并行处理可疑车辆分析
        List<TrailInfo> suspiciousVehicles = processSuspiciousVehiclesParallel(
                allTrailTracks, preloadedData, config, dateRange.formattedDate);

        // 6. 批量写入Redis
        batchWriteToRedis(suspiciousVehicles, dateRange.formattedDate);

        long duration = System.currentTimeMillis() - startTime;
        log.info("[时间分片同步] 完成，耗时: {}ms, 可疑车辆: {} 辆", duration, suspiciousVehicles.size());
    }

    // ==================== 核心辅助方法 ====================

    /**
     * 加载同步配置
     */
    private SyncConfig loadSyncConfig() {
        SyncConfig config = new SyncConfig();
        config.pageSize = "local".equals(isLocalhost) ? 6000 : 2000;
        config.starTime = 2;
        config.endTime = 4;
        config.bite = new BigDecimal("0.3");
        config.supoerMjnum = 5;
        config.roadSupoerMjnum = 3;

        // 从Redis加载配置（使用Optional简化空值处理）
        loadConfigValue(redisTimeKey).ifPresent(v -> config.starTime = Integer.parseInt(v));
        loadConfigValue(redisBiteKey).ifPresent(v -> config.bite = new BigDecimal(v));
        loadConfigValue(supoer_mjnum).ifPresent(v -> config.supoerMjnum = Integer.parseInt(v));
        loadConfigValue(road_supoer_mjnum).ifPresent(v -> config.roadSupoerMjnum = Integer.parseInt(v));

        return config;
    }

    /**
     * 从Redis加载配置值并过滤空值
     * <p>
     * 辅助方法，解决类型不匹配问题：
     * 1. 从Redis获取值（类型可能为String或其他类型）
     * 2. 统一转换为String
     * 3. 过滤空值后返回Optional
     * </p>
     * @param key Redis键
     * @return 非空配置值的Optional包装
     */
    private Optional<String> loadConfigValue(String key) {
        return Optional.ofNullable(redisCache.getCacheObject(key))
                .map(Object::toString)
                .filter(CommonUtil::isNotBlank);
    }

    /**
     * 预加载数据（一次性加载所有需要的缓存数据）
     */
    private PreloadedData preloadData() {
        PreloadedData data = new PreloadedData();

        // 并行加载多个数据源
        CompletableFuture<List<OdsSzdnGantry>> gantryFuture = CompletableFuture.supplyAsync(
                odsSzdnGantryService::getGantryRedis, executorService);

        CompletableFuture<Map<String, ZdataLocationDict>> locationFuture = CompletableFuture.supplyAsync(
                zdataLocationDictService::getRedisList, executorService);

        CompletableFuture<List<OdsSzdnSection>> sectionFuture = CompletableFuture.supplyAsync(
                sectionService::getSectionList, executorService);

        CompletableFuture.allOf(gantryFuture, locationFuture, sectionFuture).join();

        try {
            data.gantryMap = gantryFuture.get().stream()
                    .filter(g -> CommonUtil.isNotBlank(g.getGantryCode()))
                    .collect(Collectors.toMap(
                            g -> g.getGantryCode(),
                            g -> g));

            data.locationMap = locationFuture.get();

            data.sectionList = sectionFuture.get();
            data.sectionCodes = data.sectionList.stream()
                    .map(OdsSzdnSection::getSectionCode)
                    .filter(CommonUtil::isNotBlank)
                    .collect(Collectors.toSet());

            // 获取节假日配置
            String holidayValue = CommonUtil.isNull(redisCache.getCacheObject("sys_config:jholiday_time"));
            data.holidayDates = CommonUtil.isBlank(holidayValue)
                    ? new HashSet<>()
                    : Arrays.stream(holidayValue.split(","))
                            .filter(CommonUtil::isNotBlank)
                            .collect(Collectors.toSet());

        } catch (InterruptedException | ExecutionException e) {
            log.error("[预加载数据] 失败", e);
            Thread.currentThread().interrupt();
        }

        return data;
    }

    /**
     * 计算时间范围
     */
    private DateRange calculateDateRange(int starTime, int endTime) {
        DateRange range = new DateRange();
        Date now = new Date();

        // 格式化日期
        SimpleDateFormat sdf = new SimpleDateFormat("yyyyMMdd");
        range.formattedDate = sdf.format(now);

        // 计算查询日期（当前时间往前推starTime天）
        Calendar calendar = Calendar.getInstance();
        calendar.setTime(now);
        calendar.add(Calendar.DAY_OF_MONTH, -starTime);
        Date queryDate = calendar.getTime();

        SimpleDateFormat sdf1 = new SimpleDateFormat("yyyy-MM-dd");
        String dateStr = sdf1.format(queryDate);

        range.startTime = dateStr + " 00:00:00";
        range.endTime = dateStr + " 23:59:59";

        return range;
    }

    /**
     * 使用游标分页查询轨迹数据
     * <p>
     * 游标分页相比offset分页的优势：
     * 1. 避免大offset导致的全表扫描
     * 2. 性能更稳定，不受数据量影响
     * 3. 适合大数据量场景
     * </p>
     */
    private List<ZdataTrailTracks> queryTrailTracksWithCursor(DateRange dateRange, int pageSize) {
        List<ZdataTrailTracks> allResults = new ArrayList<>();
        Date lastExitTime = null;
        boolean hasMore = true;

        while (hasMore) {
            CarParaVO carParaVO = new CarParaVO();
            carParaVO.setApplyTime1(dateRange.startTime);
            carParaVO.setApplyTime2(dateRange.endTime);
            carParaVO.setPageSize(pageSize);
            carParaVO.setLastExitTime(lastExitTime); // 游标

            List<ZdataTrailTracks> pageResults = zdataTrailTracksService.getLatestTrailByCursor(carParaVO);

            if (pageResults.isEmpty() || pageResults.size() < pageSize) {
                hasMore = false;
            } else {
                lastExitTime = pageResults.get(pageResults.size() - 1).getExitTime();
            }

            allResults.addAll(pageResults);
            log.debug("[游标分页] 获取到 {} 条数据，累计 {} 条", pageResults.size(), allResults.size());
        }

        return allResults;
    }

    /**
     * 时间范围分片：将大的时间范围分割成多个小时段
     * <p>
     * 核心思路：
     * 1. 将一天的时间按小时或小时数的倍数分割
     * 2. 每个分片独立查询，避免单线程查询大量数据
     * 3. 分片数量 = CPU核心数，充分利用多核CPU
     * </p>
     *
     * @param original 原始时间范围
     * @param sliceCount 分片数量
     * @return 分片后的时间范围列表
     */
    private List<DateRange> splitDateRangeByHour(DateRange original, int sliceCount) {
        List<DateRange> ranges = new ArrayList<>();
        SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");

        try {
            Date startDate = sdf.parse(original.startTime);
            Date endDate = sdf.parse(original.endTime);

            // 计算时间跨度（毫秒）
            long totalMillis = endDate.getTime() - startDate.getTime();
            // 每个分片的时间跨度（毫秒）
            long sliceMillis = totalMillis / sliceCount;
            // 保证每个分片至少1小时
            long minSliceMillis = 60 * 60 * 1000L;
            sliceMillis = Math.max(sliceMillis, minSliceMillis);

            Calendar calendar = Calendar.getInstance();
            calendar.setTime(startDate);

            while (calendar.getTime().before(endDate)) {
                DateRange subRange = new DateRange();
                subRange.startTime = sdf.format(calendar.getTime());
                subRange.formattedDate = original.formattedDate;

                // 计算分片结束时间
                calendar.add(Calendar.MILLISECOND, (int) sliceMillis);
                Date subEnd = calendar.getTime().after(endDate) ? endDate : calendar.getTime();
                subRange.endTime = sdf.format(subEnd);

                ranges.add(subRange);
                log.debug("[时间分片] 创建分片: {} - {}", subRange.startTime, subRange.endTime);
            }

        } catch (ParseException e) {
            log.error("[时间分片] 解析时间失败", e);
            // 失败时返回原始范围作为单个分片
            ranges.add(original);
        }

        return ranges;
    }

    /**
     * 多线程并行查询多个时间分片的数据
     * <p>
     * 核心思路：
     * 1. 每个时间分片使用独立线程并行查询
     * 2. 每个分片内部使用游标分页继续优化
     * 3. 使用CompletableFuture实现非阻塞并行
     * 4. 最后合并所有结果并按时间排序
     * </p>
     *
     * @param subRanges 时间分片列表
     * @param pageSize 每页大小
     * @return 合并后的轨迹数据列表
     */
    private List<ZdataTrailTracks> queryTrailTracksParallelByRange(List<DateRange> subRanges, int pageSize) {
        // 为每个分片创建并行查询任务
        List<CompletableFuture<List<ZdataTrailTracks>>> futures = subRanges.stream()
                .map(subRange -> CompletableFuture.supplyAsync(
                        () -> {
                            log.info("[并行查询] 开始查询分片: {} - {}", subRange.startTime, subRange.endTime);
                            List<ZdataTrailTracks> result = queryTrailTracksWithCursor(subRange, pageSize);
                            log.info("[并行查询] 分片完成: {} - {}, 获取 {} 条", 
                                    subRange.startTime, subRange.endTime, result.size());
                            return result;
                        },
                        executorService))
                .collect(Collectors.toList());

        // 等待所有查询任务完成
        List<ZdataTrailTracks> allResults = futures.stream()
                .map(CompletableFuture::join)
                .flatMap(List::stream)
                // 按出站时间排序，保证数据顺序一致性
                .sorted(Comparator.comparing(ZdataTrailTracks::getExitTime))
                .collect(Collectors.toList());

        return allResults;
    }

    /**
     * 多线程并行处理可疑车辆分析
     */
    private List<TrailInfo> processSuspiciousVehiclesParallel(
            List<ZdataTrailTracks> trailTracks,
            PreloadedData preloadedData,
            SyncConfig config,
            String formattedDate) {

        // 将数据分成多个批次
        List<List<ZdataTrailTracks>> batches = partitionList(trailTracks, 1000);

        // 并行处理每个批次
        List<CompletableFuture<List<TrailInfo>>> futures = batches.stream()
                .map(batch -> CompletableFuture.supplyAsync(
                        () -> processBatch(batch, preloadedData, config, formattedDate),
                        executorService))
                .collect(Collectors.toList());

        // 等待所有任务完成并合并结果
        return futures.stream()
                .map(CompletableFuture::join)
                .flatMap(List::stream)
                .collect(Collectors.toList());
    }

    /**
     * 处理单个批次的数据
     */
    private List<TrailInfo> processBatch(
            List<ZdataTrailTracks> batch,
            PreloadedData preloadedData,
            SyncConfig config,
            String formattedDate) {

        return batch.stream()
                .filter(track -> isNonHolidayCrossProvince(track, preloadedData.holidayDates))
                .map(track -> {
                    List<TrailBo> trailBoList = parseTrailPointsJson(track.getTrailPoints());
                    return analyzeSuspiciousVehicle(track, trailBoList, preloadedData, config);
                })
                .filter(Objects::nonNull)
                .collect(Collectors.toList());
    }

    /**
     * 判断是否为非节假日的跨省车辆
     */
    private static boolean isNonHolidayCrossProvince(ZdataTrailTracks track, Set<String> holidayDates) {
        String trailtype = CommonUtil.isNull(track.getTrailtype());
        String firstName = CommonUtil.repalaceSzdnTollName(track.getEntollstationname());
        String endName = CommonUtil.repalaceSzdnTollName(track.getExtollstationname());

        // 外省进外省出的车辆
        boolean isCrossProvince = "0".equals(trailtype)
                && firstName.contains("门架")
                && endName.contains("门架");

        // 非节假日
        String enterDate = extractDate(String.valueOf(track.getEnterTime()));
        boolean isNonHoliday = !holidayDates.contains(enterDate);

        return isCrossProvince && isNonHoliday;
    }

    /**
     * 解析轨迹点JSON
     */
    private static List<TrailBo> parseTrailPointsJson(String trailPoints) {
        if (CommonUtil.isBlank(trailPoints)) {
            return new ArrayList<>();
        }
        try {
            ISysUtilService sysUtilService = SpringUtils.getBean(ISysUtilService.class);
            return sysUtilService.getTrailBoList(trailPoints);
        } catch (Exception e) {
            log.warn("[解析轨迹点] JSON解析失败: {}", e.getMessage());
            return new ArrayList<>();
        }
    }

    /**
     * 分析可疑车辆
     */
    private static TrailInfo analyzeSuspiciousVehicle(
            ZdataTrailTracks track,
            List<TrailBo> trailBoList,
            PreloadedData preloadedData,
            SyncConfig config) {

        // 统计门架抓拍和流水抓拍数量
        long gantryCaptureCount = trailBoList.stream()
                .filter(t -> "GantryCapture".equals(t.getStateType()))
                .count();

        long feeRecordCount = trailBoList.stream()
                .filter(t -> "FeeRecord".equals(t.getStateType()))
                .count();

        // 判断是否为可疑车辆
        if (gantryCaptureCount > config.supoerMjnum && feeRecordCount == 0) {
            // 构建TrailInfo
            TrailInfo trailInfo = buildTrailInfo(track, trailBoList, preloadedData);
            trailInfo.getTracks().setEscapedType(Constants.escapedType_20);
            trailInfo.getTracks().setEscapedTypeRemark(
                    "跨省全程屏蔽：门架牌识流水:" + gantryCaptureCount + "，门架交易流水:" + feeRecordCount);
            trailInfo.getTracks().setEscapedTfcj("1");

            return trailInfo;
        }

        return null;
    }

    /**
     * 构建TrailInfo
     */
    private static TrailInfo buildTrailInfo(ZdataTrailTracks track, List<TrailBo> trailBoList, PreloadedData preloadedData) {
        TrailInfo trailInfo = new TrailInfo();
        trailInfo.setTracks(track);
        trailInfo.setTrailList(trailBoList);

        // 设置轨迹UUID
        trailInfo.setTrailUuid(CommonUtil.isNull(track.getPlateKey()));

        return trailInfo;
    }

    /**
     * 批量写入Redis
     */
    private void batchWriteToRedis(List<TrailInfo> suspiciousVehicles, String formattedDate) {
        if (suspiciousVehicles.isEmpty()) {
            return;
        }

        // 批量操作优化：使用管道或批量命令
        suspiciousVehicles.forEach(trailInfo -> {
            String carNo = CommonUtil.isNull(trailInfo.getTrailUuid());
            String key = Constants.car_uspicious + formattedDate + ":" + carNo;
            redisCache.setCacheObject(key, trailInfo);
        });

        log.info("[批量写入Redis] 写入 {} 条数据", suspiciousVehicles.size());
    }

    /**
     * 将列表分成指定大小的批次
     */
    private <T> List<List<T>> partitionList(List<T> list, int batchSize) {
        return list.stream()
                .collect(Collectors.groupingBy(i -> list.indexOf(i) / batchSize))
                .values()
                .stream()
                .map(ArrayList::new)
                .collect(Collectors.toList());
    }

    /**
     * 从时间字符串中提取日期
     */
    private static String extractDate(String datetime) {
        if (CommonUtil.isBlank(datetime)) {
            return "";
        }
        return datetime.substring(0, 10);
    }

    /**
     * 过滤非节假日的跨省车辆（用于流式处理）
     */
    private boolean filterNonHolidayCrossProvince(ZdataTrailTracks track, Set<String> holidayDates) {
        return isNonHolidayCrossProvince(track, holidayDates);
    }

    /**
     * 解析轨迹点（用于流式处理）
     */
    private TrackTrailTuple parseTrailPoints(ZdataTrailTracks track, Set<String> sectionCodes) {
        TrackTrailTuple tuple = new TrackTrailTuple();
        tuple.tracks = track;
        tuple.trailBoList = parseTrailPointsJson(track.getTrailPoints());
        return tuple;
    }

    /**
     * 判断是否为可疑车辆（用于流式处理）
     */
    private boolean isSuspiciousVehicle(TrackTrailTuple tuple, SyncConfig config) {
        long gantryCount = tuple.trailBoList.stream()
                .filter(t -> "GantryCapture".equals(t.getStateType()))
                .count();
        long feeCount = tuple.trailBoList.stream()
                .filter(t -> "FeeRecord".equals(t.getStateType()))
                .count();
        return gantryCount > config.supoerMjnum && feeCount == 0;
    }

    // ==================== 内部类 ====================

    /**
     * 同步配置
     */
    private static class SyncConfig {
        int pageSize;
        int starTime;
        int endTime;
        BigDecimal bite;
        int supoerMjnum;
        int roadSupoerMjnum;
    }

    /**
     * 预加载数据
     */
    private static class PreloadedData {
        Map<String, OdsSzdnGantry> gantryMap;
        Map<String, ZdataLocationDict> locationMap;
        List<OdsSzdnSection> sectionList;
        Set<String> sectionCodes;
        Set<String> holidayDates;
    }

    /**
     * 时间范围
     */
    private static class DateRange {
        String startTime;
        String endTime;
        String formattedDate;
    }

    /**
     * 轨迹和轨迹点的元组（用于流式处理）
     */
    private static class TrackTrailTuple {
        ZdataTrailTracks tracks;
        List<TrailBo> trailBoList;
    }

    /**
     * ForkJoin任务：并行处理可疑车辆
     */
    private static class SuspiciousVehicleTask extends RecursiveTask<List<TrailInfo>> {
        private static final int THRESHOLD = 1000;
        private final List<ZdataTrailTracks> trailTracks;
        private final int start;
        private final int end;
        private final PreloadedData preloadedData;
        private final SyncConfig config;
        private final String formattedDate;

        SuspiciousVehicleTask(List<ZdataTrailTracks> trailTracks, int start, int end,
                             PreloadedData preloadedData, SyncConfig config, String formattedDate) {
            this.trailTracks = trailTracks;
            this.start = start;
            this.end = end;
            this.preloadedData = preloadedData;
            this.config = config;
            this.formattedDate = formattedDate;
        }

        @Override
        protected List<TrailInfo> compute() {
            if (end - start <= THRESHOLD) {
                // 直接处理
                return processSubList(trailTracks.subList(start, end));
            }

            // 分治处理
            int mid = (start + end) / 2;
            SuspiciousVehicleTask left = new SuspiciousVehicleTask(
                    trailTracks, start, mid, preloadedData, config, formattedDate);
            SuspiciousVehicleTask right = new SuspiciousVehicleTask(
                    trailTracks, mid, end, preloadedData, config, formattedDate);

            left.fork();
            List<TrailInfo> rightResult = right.compute();
            List<TrailInfo> leftResult = left.join();

            // 合并结果
            List<TrailInfo> result = new ArrayList<>(leftResult);
            result.addAll(rightResult);
            return result;
        }

        private List<TrailInfo> processSubList(List<ZdataTrailTracks> subList) {
            return subList.stream()
                    .filter(track -> isNonHolidayCrossProvince(track, preloadedData.holidayDates))
                    .map(track -> {
                        List<TrailBo> trailBoList = parseTrailPointsJson(track.getTrailPoints());
                        return analyzeSuspiciousVehicle(track, trailBoList, preloadedData, config);
                    })
                    .filter(Objects::nonNull)
                    .collect(Collectors.toList());
        }
    }
}
