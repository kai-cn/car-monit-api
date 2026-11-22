package com.ruoyi.base.service.v3.query;

import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import com.ruoyi.base.service.v3.es.TrafficEsIndexService;
import com.ruoyi.base.service.v3.model.TrafficTable;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 查询引擎安全切换：默认 legacy；显式配置 es 时启动就绪检测，缺失则自动回退并 WARN。
 *
 * <p>就绪条件（全部满足才启用 es）：</p>
 * <ul>
 *   <li>ES 可 ping 通；</li>
 *   <li>三张表的读别名 {@code *-read} 存在；</li>
 *   <li>三张表的当月索引存在（避免“别名存在但缺当月索引”导致近期数据漏查）。</li>
 * </ul>
 *
 * <p>运行期 ES 故障不会自动回退 GaussDB（设计禁止模糊回退）；运维可调用
 * {@code POST /api/v3/es/activate?engine=legacy} 立即降级，或恢复 ES 后再 activate=es。</p>
 */
@Slf4j
@Service
public class TrafficQueryEngineService {

    public static final String ENGINE_ES = "es";
    public static final String ENGINE_LEGACY = "legacy";

    private final TrafficV3Properties properties;
    private final TrafficEsIndexService indexService;

    private volatile String configuredEngine = ENGINE_LEGACY;
    private volatile String activeEngine = ENGINE_LEGACY;
    private volatile String readinessMessage = "未执行就绪检测";

    public TrafficQueryEngineService(TrafficV3Properties properties,
                                     TrafficEsIndexService indexService) {
        this.properties = properties;
        this.indexService = indexService;
    }

    /**
     * Spring 上下文就绪后执行一次检测；此时数据源/ES 客户端均已初始化。
     */
    @EventListener(ApplicationReadyEvent.class)
    public void onApplicationReady() {
        String cfg = normalize(properties.getQuery().getEngine());
        configuredEngine = cfg;
        if (!ENGINE_ES.equals(cfg) && !ENGINE_LEGACY.equals(cfg)) {
            configuredEngine = ENGINE_LEGACY;
            activeEngine = ENGINE_LEGACY;
            readinessMessage = "非法 traffic.query.engine=" + cfg + "，已回退 legacy";
            log.warn("[V3引擎] 非法配置 {}，使用安全默认 legacy", cfg);
            return;
        }
        if (ENGINE_LEGACY.equals(cfg)) {
            activeEngine = ENGINE_LEGACY;
            readinessMessage = "配置为 legacy，不做 ES 就绪检测";
            log.info("[V3引擎] 当前使用 legacy（安全默认）。ES 初始化完成后可切换 es");
            return;
        }
        Readiness readiness = checkReadiness();
        if (readiness.ready) {
            activeEngine = ENGINE_ES;
            readinessMessage = readiness.message;
            log.info("[V3引擎] 配置 es 且就绪检测通过，已启用 ES 主路径");
        } else {
            activeEngine = ENGINE_LEGACY;
            readinessMessage = readiness.message;
            log.warn("[V3引擎] 配置 es 但就绪检测未通过，已自动回退 legacy：{}", readiness.message);
        }
    }

    public boolean isEsActive() {
        return ENGINE_ES.equals(activeEngine);
    }

    public String getConfiguredEngine() {
        return configuredEngine;
    }

    public String getActiveEngine() {
        return activeEngine;
    }

    /**
     * 运维显式切换（运行期生效，不修改配置文件；重启后按配置重新检测）。
     */
    public synchronized Map<String, Object> activate(String engine) {
        String target = normalize(engine);
        Map<String, Object> result = new LinkedHashMap<>();
        if (!ENGINE_ES.equals(target) && !ENGINE_LEGACY.equals(target)) {
            result.put("success", false);
            result.put("message", "engine 仅支持 es/legacy");
            return result;
        }
        if (ENGINE_LEGACY.equals(target)) {
            activeEngine = ENGINE_LEGACY;
            readinessMessage = "运维手动切换 legacy";
            log.warn("[V3引擎] 运维手动切换为 legacy");
            result.put("success", true);
            result.put("activeEngine", activeEngine);
            result.put("message", "已切换 legacy");
            return result;
        }

        Readiness readiness = checkReadiness();
        if (!readiness.ready) {
            activeEngine = ENGINE_LEGACY;
            readinessMessage = readiness.message;
            log.warn("[V3引擎] 切换 es 失败，保持 legacy：{}", readiness.message);
            result.put("success", false);
            result.put("activeEngine", activeEngine);
            result.put("message", "ES 未就绪，保持 legacy: " + readiness.message);
            return result;
        }
        activeEngine = ENGINE_ES;
        readinessMessage = readiness.message;
        log.info("[V3引擎] 运维手动切换为 es，就绪检测通过");
        result.put("success", true);
        result.put("activeEngine", activeEngine);
        result.put("message", "已切换 es");
        return result;
    }

    /**
     * 返回给运维接口的详细就绪信息。
     */
    public Map<String, Object> readinessView() {
        Map<String, Object> view = new LinkedHashMap<>();
        view.put("configuredEngine", configuredEngine);
        view.put("activeEngine", activeEngine);
        view.put("message", readinessMessage);
        Readiness readiness = checkReadiness();
        view.put("ready", readiness.ready);
        view.put("esAvailable", readiness.esAvailable);
        view.put("readAliases", readiness.readAliases);
        view.put("currentIndices", readiness.currentIndices);
        view.put("writeAliases", readiness.writeAliases);
        return view;
    }

    private Readiness checkReadiness() {
        Readiness readiness = new Readiness();
        readiness.esAvailable = indexService.ping();
        if (!readiness.esAvailable) {
            readiness.message = "ES 不可达";
            return readiness;
        }

        StringBuilder missing = new StringBuilder();
        readiness.ready = true;
        for (TrafficTable table : TrafficTable.values()) {
            String key = table.getParamName();
            boolean readAlias = indexService.readAliasExists(table);
            boolean currentIndex = indexService.currentIndexExists(table);
            boolean writeAlias = indexService.writeAliasExists(table);
            readiness.readAliases.put(key, readAlias);
            readiness.currentIndices.put(key, currentIndex);
            readiness.writeAliases.put(key, writeAlias);
            if (!readAlias || !currentIndex) {
                readiness.ready = false;
                if (missing.length() > 0) {
                    missing.append(", ");
                }
                missing.append(key)
                        .append("(readAlias=").append(readAlias)
                        .append(", currentIndex=").append(currentIndex).append(')');
            }
        }
        readiness.message = readiness.ready
                ? "ES 可读且三表读别名/当月索引均存在"
                : "ES 就绪项缺失: " + missing;
        return readiness;
    }

    private String normalize(String engine) {
        return engine == null ? ENGINE_LEGACY : engine.trim().toLowerCase();
    }

    private static class Readiness {
        private boolean ready;
        private boolean esAvailable;
        private String message;
        private final Map<String, Boolean> readAliases = new LinkedHashMap<>();
        private final Map<String, Boolean> currentIndices = new LinkedHashMap<>();
        private final Map<String, Boolean> writeAliases = new LinkedHashMap<>();
    }
}
