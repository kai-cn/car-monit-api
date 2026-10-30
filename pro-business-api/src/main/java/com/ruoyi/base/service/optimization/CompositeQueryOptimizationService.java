package com.ruoyi.base.service.optimization;

import com.ruoyi.base.domain.*;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.concurrent.*;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 方案三：组合优化查询 - 智能路由服务
 * <p>
 * 核心思路：
 *   根据查询条件，智能选择最优的查询策略，实现降级和并行查询
 * <p>
 * 查询策略选择逻辑：
 *   | 条件                    | 首选方案       | 降级方案             |
 *   | 完整车牌号               | ES termQuery   | GaussDB B-tree索引    |
 *   | 车牌号前缀(3-6位)        | ES prefixQuery | GaussDB GIN 索引       |
 *   | 全模糊查询 like '%赣%'   | ES wildcard    | GaussDB pg_trgm GIN   |
 *   | 时间范围小（1-7天）      | GaussDB 分区表  | ES                     |
 *   | 时间范围大（1-6个月）    | ES             | 多分区并行查询         |
 *   | 多字段组合查询（推荐）    | ES boolQuery   | GIN+组合索引           |
 * <p>
 * 性能目标：
 *   - 90%的查询响应时间 < 500ms
 *   - 99%的查询响应时间 < 3秒
 *   - 最大查询响应时间 < 30秒（否则超时降级）
 */
@Slf4j
@Service
public class CompositeQueryOptimizationService {

    @Value("${optimization.query.route.es:true}")
    private boolean esRouteEnabled;

    @Value("${optimization.query.route.parallel:true}")
    private boolean parallelEnabled;

    @Value("${optimization.query.timeout-ms:30000}")
    private int queryTimeoutMs;

    /**
     * 线程池大小（根据查询策略调整）
     */
    private static final int POOL_SIZE = 8;
    private final ExecutorService executorService = new ThreadPoolExecutor(
            POOL_SIZE,
            POOL_SIZE,
            60L,
            TimeUnit.SECONDS,
            new LinkedBlockingQueue<>(1000),
            new ThreadPoolExecutor.CallerRunsPolicy()
    );

    @Autowired
    private ElasticsearchQueryService esQueryService;

    @Autowired
    private LargeTableQueryOptimizationService dbQueryService;

    @Autowired
    private QueryValidationService queryValidationService;

    /**
     * 车牌号正则（完整车牌）
     */
    private static final Pattern FULL_PLATE_PATTERN = Pattern.compile(
            "^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领][A-Z][A-Z0-9]{5,6}$");

    /**
     * 门架抓拍流水 - 组合查询入口
     *
     * 根据查询条件智能选择：
     *   1. 参数校验：强制时间范围、限制深分页
     *   2. 模糊查询检测：LIKE '%xxx%' 走 ES
     *   3. 完整车牌+短时间范围 -> DB (B-tree 精确匹配)
     *   4. 完整车牌+长时间范围 -> ES
     *   5. 模糊/部分车牌 -> 全走 ES
     *   6. 降级策略：ES失败 -> 数据库
     */
    public List<OdsRtSzdnSnapshotFlowAddcode> querySnapshotFlow(
            String startTime,
            String endTime,
            String plateNumber,
            String gantryCode,
            String sectionCode,
            String orgCode,
            int pageNum,
            int pageSize
    ) {
        // ============== 1. 参数校验 ==============
        QueryValidationService.ValidationResult validation =
                queryValidationService.validatePageQuery(startTime, endTime, pageNum, pageSize);
        if (!validation.isValid()) {
            log.warn("[组合查询] 参数校验失败: {}", validation.getErrorMessage());
            throw new RuntimeException(validation.getErrorMessage());
        }

        // ============== 2. 智能路由决策 ==============
        QueryStrategy strategy = decideStrategy(
                startTime, endTime, plateNumber, gantryCode, sectionCode);
        log.info("[组合查询] 智能路由策略 strategy={}, plate={}, timeRange={}天, validation={}",
                strategy, plateNumber, validation.getTimeRangeDays(), validation);

        // ============== 3. 执行查询 ==============
        switch (strategy) {
            case ES_ONLY:
                return esQueryService.querySnapshotFlowByEs(startTime, endTime, plateNumber, gantryCode, sectionCode, orgCode, pageNum, pageSize);
            case DB_ONLY:
                return dbQueryService.querySnapshotFlowOptimized(startTime, endTime, plateNumber, gantryCode, sectionCode, orgCode);
            case ES_FIRST_THEN_DB:
            default:
                return parallelOrFallbackQuery(startTime, endTime, plateNumber, gantryCode, sectionCode, orgCode, pageNum, pageSize);
        }
    }

    /**
     * 决策：根据查询条件选择最优策略
     *
     * 规则：
     *   1. 完整车牌号(7-8位) - 优先级高的等值查询：ES_FIRST_THEN_DB
     *   2. 全模糊查询（如 "赣", "A1"）且时间范围大 - 用ES
     *   3. 有明确的 gantrycode/sectioncode/orgcode 且时间范围 <=7天 - 用DB
     *   4. 默认 - ES_FIRST_THEN_DB
     */
    private QueryStrategy decideStrategy(String startTime, String endTime, String plateNumber,
                                          String gantryCode, String sectionCode) {
        // 条件1：完整车牌 - ES优先
        boolean isFullPlate = plateNumber != null && plateNumber.length() >= 7;
        // 条件2：精确字段是否有值
        boolean hasExactField = (gantryCode != null && !gantryCode.isEmpty())
                || (sectionCode != null && !sectionCode.isEmpty());
        // 条件3：估算时间范围天数
        int timeRangeDays = estimateDayRange(startTime, endTime);

        if (!esRouteEnabled) {
            return QueryStrategy.DB_ONLY;
        }

        // 完整车牌 - ES
        if (isFullPlate) {
            return QueryStrategy.ES_FIRST_THEN_DB;
        }

        // 有精确字段且时间范围<=7天 - DB
        if (hasExactField && timeRangeDays <= 7 && timeRangeDays > 0) {
            return QueryStrategy.DB_ONLY;
        }

        // 时间范围大 - ES优先
        if (timeRangeDays > 30) {
            return QueryStrategy.ES_FIRST_THEN_DB;
        }

        // 全模糊查询 - ES_FIRST_THEN_DB
        return QueryStrategy.ES_FIRST_THEN_DB;
    }

    /**
     * 并行或降级查询：先查 ES，失败则查询数据库
     */
    private List<OdsRtSzdnSnapshotFlowAddcode> parallelOrFallbackQuery(
            String startTime, String endTime, String plateNumber, String gantryCode,
            String sectionCode, String orgCode, int pageNum, int pageSize) {

        Future<List<OdsRtSzdnSnapshotFlowAddcode>> esFuture = null;
        Future<List<OdsRtSzdnSnapshotFlowAddcode>> dbFuture = null;

        try {
            // 并行查询策略：ES和数据库并行查询，先返回的优先
            if (parallelEnabled) {
                esFuture = executorService.submit(() -> {
                    try {
                        return esQueryService.querySnapshotFlowByEs(startTime, endTime, plateNumber, gantryCode, sectionCode, orgCode, pageNum, pageSize);
                    } catch (Exception e) {
                        log.warn("[组合查询] ES 并行查询失败", e);
                        return Collections.emptyList();
                    }
                });

                dbFuture = executorService.submit(() -> {
                    try {
                        return dbQueryService.querySnapshotFlowOptimized(startTime, endTime, plateNumber, gantryCode, sectionCode, orgCode);
                    } catch (Exception e) {
                        log.warn("[组合查询] DB 并行查询失败", e);
                        return Collections.emptyList();
                    }
                });

                // ES优先，成功直接返回
                List<OdsRtSzdnSnapshotFlowAddcode> esResult = esFuture.get(queryTimeoutMs, TimeUnit.MILLISECONDS);
                if (esResult != null && !esResult.isEmpty()) {
                    log.info("[组合查询] ES查询成功，返回结果 size={}", esResult.size());
                    return esResult;
                }

                // ES查询为空，返回DB
                List<OdsRtSzdnSnapshotFlowAddcode> dbResult = dbFuture.get(queryTimeoutMs, TimeUnit.MILLISECONDS);
                log.info("[组合查询] ES为空，返回DB查询结果 size={}", dbResult.size());
                return dbResult;
            } else {
                // 串行：先ES后降级
                List<OdsRtSzdnSnapshotFlowAddcode> esResult = esQueryService.querySnapshotFlowByEs(startTime, endTime, plateNumber, gantryCode, sectionCode, orgCode, pageNum, pageSize);
                if (esResult != null && !esResult.isEmpty()) {
                    return esResult;
                }
                return dbQueryService.querySnapshotFlowOptimized(startTime, endTime, plateNumber, gantryCode, sectionCode, orgCode);
            }
        } catch (TimeoutException e) {
            log.error("[组合查询] 查询超时 timeOut={}ms", queryTimeoutMs, e);
            return Collections.emptyList();
        } catch (Exception e) {
            log.error("[组合查询] 查询异常", e);
            return Collections.emptyList();
        }
    }

    /**
     * 估算时间范围的天数 - 用于路由决策
     */
    private int estimateDayRange(String startTime, String endTime) {
        try {
            if (startTime == null || endTime == null) {
                return Integer.MAX_VALUE;
            }
            // 简化：解析时间字符串并计算天数差
            java.time.LocalDateTime start = java.time.LocalDateTime.parse(startTime, java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
            java.time.LocalDateTime end = java.time.LocalDateTime.parse(endTime, java.time.format.DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss"));
            return (int) java.time.Duration.between(start, end).toDays() + 1;
        } catch (Exception e) {
            return Integer.MAX_VALUE;
        }
    }

    /**
     * 交易流水 - 组合查询入口
     */
    public List<OdsLwzxsfsjFeeRecords01> queryFeeRecords(
            String startTime, String endTime, String vehiclePlate, String gantryId,
            String sectionCode, int pageNum, int pageSize) {
        QueryStrategy strategy = decideStrategy(startTime, endTime, vehiclePlate, gantryId, sectionCode);
        log.info("[组合查询-交易] 策略 strategy={}", strategy);

        switch (strategy) {
            case ES_ONLY:
            case ES_FIRST_THEN_DB:
                List<OdsLwzxsfsjFeeRecords01> esResult = esQueryService.queryFeeRecordsByEs(startTime, endTime, vehiclePlate, gantryId, sectionCode, pageNum, pageSize);
                if (esResult != null && !esResult.isEmpty()) {
                    return esResult;
                }
                // 降级
                return dbQueryService.queryFeeRecordsOptimized(startTime, endTime, vehiclePlate, gantryId);
            case DB_ONLY:
            default:
                return dbQueryService.queryFeeRecordsOptimized(startTime, endTime, vehiclePlate, gantryId);
        }
    }

    /**
     * 轨迹数据 - 组合查询入口
     */
    public List<ZdataTrailFitting> queryTrailFitting(
            String startTime, String endTime, String envehicleid, String stationName,
            int pageNum, int pageSize) {
        QueryStrategy strategy = decideStrategy(startTime, endTime, envehicleid, null, null);
        log.info("[组合查询-轨迹] 策略 strategy={}", strategy);

        switch (strategy) {
            case ES_ONLY:
            case ES_FIRST_THEN_DB:
                List<ZdataTrailFitting> esResult = esQueryService.queryTrailFittingByEs(startTime, endTime, envehicleid, stationName, pageNum, pageSize);
                if (esResult != null && !esResult.isEmpty()) {
                    return esResult;
                }
                return dbQueryService.queryTrailFittingOptimized(startTime, endTime, envehicleid, stationName);
            case DB_ONLY:
            default:
                return dbQueryService.queryTrailFittingOptimized(startTime, endTime, envehicleid, stationName);
        }
    }

    /**
     * 查询策略枚举
     */
    public enum QueryStrategy {
        /**
         * 仅ES查询 - 性能最高
         */
        ES_ONLY,
        /**
         * 仅数据库查询 - 精确匹配小范围
         */
        DB_ONLY,
        /**
         * ES优先，失败降级到数据库
         */
        ES_FIRST_THEN_DB,
        /**
         * ES和数据库并行查询，取最快结果
         */
        PARALLEL_QUERY
    }

    /**
     * 查询状态健康检查
     */
    public Map<String, Object> healthCheck() {
        Map<String, Object> health = new HashMap<>();
        health.put("esAvailable", esQueryService.checkHealth());
        health.put("dbRouteEnabled", esRouteEnabled);
        health.put("parallelEnabled", parallelEnabled);
        health.put("queryTimeoutMs", queryTimeoutMs);
        return health;
    }
}
