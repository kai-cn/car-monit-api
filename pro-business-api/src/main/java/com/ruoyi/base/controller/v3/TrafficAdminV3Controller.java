package com.ruoyi.base.controller.v3;

import com.ruoyi.base.service.v3.bigscreen.DwsEtlService;
import com.ruoyi.base.service.v3.es.CarWarningBackfillService;
import com.ruoyi.base.service.v3.es.TrafficEsIndexService;
import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.query.TrafficQueryEngineService;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import com.ruoyi.base.service.v3.sync.CarWarningChangeProducer;
import com.ruoyi.base.service.v3.sync.BackfillTask;
import com.ruoyi.base.service.v3.sync.EsBackfillService;
import com.ruoyi.base.service.v3.sync.OutboxRelayService;
import com.ruoyi.base.service.v3.sync.TrafficReconciliationService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * V3 运维接口：ES 初始化、回灌、对账、Outbox relay 手动触发。
 *
 * <p><b>安全警告（P1-12）：本类端点当前无鉴权</b>（工程内 SecurityInterceptor/WebConfig
 * 仍被注释，见 docs/v3-auth-options.md）。这些端点可切换查询引擎、触发重负载回灌、
 * 删除 ES 孤儿文档，<b>禁止在对内网以外的任何网络暴露</b>；生产必须先做网络隔离
 * （内网绑定/安全组/网关认证）再上线。</p>
 */
@Slf4j
@RestController
@RequestMapping("/api/v3")
public class TrafficAdminV3Controller {

    private final TrafficEsIndexService indexService;
    private final TrafficQueryEngineService queryEngineService;
    private final EsBackfillService backfillService;
    private final CarWarningBackfillService carWarningBackfillService;
    private final DwsEtlService dwsEtlService;
    private final CarWarningChangeProducer carWarningChangeProducer;
    private final TrafficReconciliationService reconciliationService;
    private final OutboxRelayService outboxRelayService;

    public TrafficAdminV3Controller(TrafficEsIndexService indexService,
                                    TrafficQueryEngineService queryEngineService,
                                    EsBackfillService backfillService,
                                    CarWarningBackfillService carWarningBackfillService,
                                    DwsEtlService dwsEtlService,
                                    CarWarningChangeProducer carWarningChangeProducer,
                                    TrafficReconciliationService reconciliationService,
                                    OutboxRelayService outboxRelayService) {
        this.indexService = indexService;
        this.queryEngineService = queryEngineService;
        this.backfillService = backfillService;
        this.carWarningBackfillService = carWarningBackfillService;
        this.dwsEtlService = dwsEtlService;
        this.carWarningChangeProducer = carWarningChangeProducer;
        this.reconciliationService = reconciliationService;
        this.outboxRelayService = outboxRelayService;
    }

    /** 创建 ILM + 模板 + 最近 N 个月索引/别名（幂等） */
    @PostMapping("/es/bootstrap")
    public Map<String, Object> bootstrap(
            @RequestParam(defaultValue = "13") int monthsBack,
            @RequestParam(defaultValue = "1") int monthsForward) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            result.put("code", 200);
            result.put("message", "ok");
            result.put("data", indexService.bootstrap(monthsBack, monthsForward));
        } catch (Exception e) {
            log.error("[V3运维] ES 初始化失败", e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /** ES 健康与当前索引名 */
    @GetMapping("/es/status")
    public Map<String, Object> esStatus() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("code", 200);
        result.put("available", indexService.ping());
        result.put("configuredEngine", queryEngineService.getConfiguredEngine());
        result.put("activeEngine", queryEngineService.getActiveEngine());
        Map<String, Object> indices = new LinkedHashMap<>();
        for (TrafficTable table : TrafficTable.values()) {
            Map<String, String> item = new LinkedHashMap<>();
            item.put("currentIndex", indexService.currentIndexName(table));
            item.put("readAlias", table.readAlias());
            item.put("writeAlias", table.writeAlias());
            indices.put(table.getParamName(), item);
        }
        result.put("indices", indices);
        return result;
    }

    /**
     * 查询引擎就绪信息：ES 可达、三表读别名/当月索引是否齐全。
     * 供 es-init.ps1 / 运维在切换 es 前确认。
     */
    @GetMapping("/es/readiness")
    public Map<String, Object> readiness() {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("code", 200);
        result.put("data", queryEngineService.readinessView());
        return result;
    }

    /**
     * 显式切换查询引擎（运行期生效，不修改配置文件）。
     * engine=es 时先做就绪检测，不通过则保持 legacy；engine=legacy 立即降级。
     */
    @PostMapping("/es/activate")
    public Map<String, Object> activate(@RequestParam(defaultValue = "es") String engine) {
        Map<String, Object> result = new LinkedHashMap<>();
        Map<String, Object> activation = queryEngineService.activate(engine);
        boolean success = Boolean.TRUE.equals(activation.get("success"));
        result.put("code", success ? 200 : 409);
        result.putAll(activation);
        return result;
    }

    /**
     * 创建 car-warning 实时预警索引（模板由 /es/bootstrap 一并写入）。
     */
    @PostMapping("/es/car-warning/bootstrap")
    public Map<String, Object> bootstrapCarWarning() {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            boolean created = indexService.ensureCarWarningIndex();
            result.put("code", 200);
            result.put("index", TrafficEsIndexService.CAR_WARNING_INDEX);
            result.put("status", created ? "created" : "exists");
        } catch (Exception e) {
            log.error("[V3运维] car-warning 索引创建失败", e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * car-warning 回灌（阶段一运维入口；数据源 car_warning_info，可选 join car_info）。
     */
    @PostMapping("/sync/car-warning/backfill")
    public Map<String, Object> backfillCarWarning(
            @RequestParam String startTime,
            @RequestParam String endTime,
            @RequestParam(defaultValue = "1000") int limit) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            Map<String, Object> data = carWarningBackfillService.backfill(startTime, endTime, limit);
            result.put("code", 200);
            result.put("message", "car-warning 回灌完成");
            result.put("data", data);
        } catch (Exception e) {
            log.error("[V3运维] car-warning 回灌失败", e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 大屏 DWS 预聚合批量回填（MySQL -> GaussDB）。
     * 时间格式：yyyy-MM-dd HH:mm:ss 或 yyyy-MM-dd。
     */
    @PostMapping("/sync/dws/backfill")
    public Map<String, Object> backfillDws(
            @RequestParam String startTime,
            @RequestParam String endTime) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            result.put("code", 200);
            result.put("message", "DWS 回填完成");
            result.put("data", dwsEtlService.backfill(startTime, endTime));
        } catch (Exception e) {
            log.error("[V3运维] DWS 回填失败", e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * car-warning 增量采集一次（MySQL update_time -> GaussDB outbox），
     * 后续由 OutboxRelay 发 Kafka、SearchSyncConsumer 写入 ES。
     */
    @PostMapping("/sync/car-warning/outbox/poll")
    public Map<String, Object> pollCarWarningOutbox() {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            result.put("code", 200);
            result.put("message", "car-warning 增量采集完成");
            result.put("data", carWarningChangeProducer.poll());
        } catch (Exception e) {
            log.error("[V3运维] car-warning 增量采集失败", e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /**
     * 提交回灌任务（GaussDB -> ES，幂等 bulk）。
     * 时间格式：yyyy-MM-dd HH:mm:ss 或 yyyy-MM-dd。
     */
    @PostMapping("/sync/backfill")
    public Map<String, Object> backfill(
            @RequestParam String table,
            @RequestParam String startTime,
            @RequestParam String endTime) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            TrafficTable t = TrafficTable.fromParam(table);
            long start = TrafficTimeUtils.parse(startTime, false);
            long end = TrafficTimeUtils.parse(endTime, true);
            BackfillTask task = backfillService.submit(t, start, end);
            result.put("code", 200);
            result.put("message", "回灌任务已提交");
            result.put("taskId", task.getTaskId());
            result.put("table", t.getParamName());
        } catch (Exception e) {
            log.error("[V3运维] 回灌提交失败", e);
            result.put("code", 500);
            result.put("message", e.getMessage());
        }
        return result;
    }

    @GetMapping("/sync/backfill/status/{taskId}")
    public Map<String, Object> backfillStatus(@PathVariable String taskId) {
        Map<String, Object> result = new LinkedHashMap<>();
        BackfillTask task = backfillService.get(taskId);
        if (task == null) {
            result.put("code", 404);
            result.put("message", "task not found");
            return result;
        }
        result.put("code", 200);
        result.put("data", task);
        return result;
    }

    /**
     * 手动触发对账：默认最近窗口；传 startTime/endTime 可对历史区间做分钟桶对账。
     * 时间格式：yyyy-MM-dd HH:mm:ss 或 yyyy-MM-dd。
     */
    @PostMapping("/sync/reconcile")
    public Map<String, Object> reconcile(
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            @RequestParam(defaultValue = "0") int bucketMinutes) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            Map<String, Object> summary;
            if (startTime != null && endTime != null) {
                Long start = TrafficTimeUtils.parse(startTime, false);
                Long end = TrafficTimeUtils.parse(endTime, true);
                if (start == null || end == null) {
                    throw new IllegalArgumentException("时间格式非法，支持 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss");
                }
                summary = bucketMinutes > 0
                        ? reconciliationService.reconcileRange(start, end, bucketMinutes)
                        : reconciliationService.reconcileRange(start, end);
            } else {
                summary = reconciliationService.reconcileLastWindow();
            }
            result.put("code", 200);
            result.put("message", "对账完成");
            result.put("data", summary);
        } catch (Exception e) {
            log.error("[V3运维] 手工对账失败", e);
            result.put("code", 400);
            result.put("message", e.getMessage());
        }
        return result;
    }

    /** 手动触发 Outbox relay（需 traffic.sync.enabled=true） */
    @PostMapping("/sync/outbox/relay")
    public Map<String, Object> relay() {
        Map<String, Object> result = new LinkedHashMap<>();
        outboxRelayService.relay();
        result.put("code", 200);
        result.put("message", "relay 已执行一次");
        return result;
    }

    /**
     * P1-7：清理指定时间窗内“ES 存在但 GaussDB 不存在”的孤儿文档。
     * 对账只在漂移桶自动清理；此接口用于历史区间的定向修复。
     */
    @PostMapping("/sync/reconcile/orphans")
    public Map<String, Object> sweepOrphans(
            @RequestParam String table,
            @RequestParam String startTime,
            @RequestParam String endTime) {
        Map<String, Object> result = new LinkedHashMap<>();
        try {
            TrafficTable t = TrafficTable.fromParam(table);
            Long start = TrafficTimeUtils.parse(startTime, false);
            Long end = TrafficTimeUtils.parse(endTime, true);
            if (start == null || end == null) {
                throw new IllegalArgumentException("时间格式非法，支持 yyyy-MM-dd 或 yyyy-MM-dd HH:mm:ss");
            }
            int deleted = reconciliationService.sweepOrphanDocs(t, start, end);
            result.put("code", 200);
            result.put("message", "孤儿文档清理完成");
            result.put("table", t.getParamName());
            result.put("deleted", deleted);
        } catch (Exception e) {
            log.error("[V3运维] 孤儿清理失败", e);
            result.put("code", 400);
            result.put("message", e.getMessage());
        }
        return result;
    }
}
