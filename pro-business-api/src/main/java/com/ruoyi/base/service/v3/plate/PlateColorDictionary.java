package com.ruoyi.base.service.v3.plate;

import com.ruoyi.base.service.v3.config.TrafficV3Properties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.DriverManagerDataSource;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * 车牌颜色字典（单一事实源：MySQL carmonitdb.sys_dict_type / sys_dict_data，
 * dict_type=plate_color）。
 *
 * <p>实测条目：0=蓝色、1=黄色、3=黑色、6=白色、5=绿色、7=临时、
 * 93=黄绿双拼底黑字、4=渐变绿底黑字、9=其他。0 是合法码。</p>
 *
 * <p>加载策略：启动加载 + 每 5 分钟定时刷新 + 内存原子快照；MySQL 不可用时保留
 * 上一次成功快照。**代码内不再维护任何颜色码兜底表**；若从未加载成功，所有颜色码
 * 视为未知（-1），并在日志/导出中明确展示“未知”。</p>
 */
@Slf4j
@Component
public class PlateColorDictionary {

    private static final String QUERY_SQL =
            "SELECT d.dict_value, d.dict_label, d.dict_sort "
                    + "FROM sys_dict_data d "
                    + "JOIN sys_dict_type t ON t.dict_type = d.dict_type "
                    + "WHERE d.dict_type = ? AND d.status = '0' AND t.status = '0' "
                    + "ORDER BY d.dict_sort, d.dict_code";

    private final TrafficV3Properties properties;
    private final AtomicBoolean refreshing = new AtomicBoolean(false);

    private volatile Snapshot snapshot = Snapshot.empty();

    public PlateColorDictionary(TrafficV3Properties properties) {
        this.properties = properties;
    }

    @PostConstruct
    public void init() {
        refresh();
    }

    /**
     * 定时刷新；与启动加载共用同一逻辑。刷新失败保留旧快照。
     */
    @Scheduled(fixedDelayString = "${traffic.plate.color.dict.refresh-interval-ms:300000}")
    public void scheduledRefresh() {
        refresh();
    }

    public synchronized void refresh() {
        TrafficV3Properties.Plate.Color.Dict config = properties.getPlate().getColor().getDict();
        if (config == null || !config.isEnabled()) {
            log.warn("[V3车牌] plate_color 字典加载已关闭（traffic.plate.color.dict.enabled=false）");
            return;
        }
        if (!refreshing.compareAndSet(false, true)) {
            return;
        }
        try {
            DriverManagerDataSource dataSource = new DriverManagerDataSource(
                    config.getUrl(), config.getUsername(), config.getPassword());
            dataSource.setDriverClassName("com.mysql.cj.jdbc.Driver");
            JdbcTemplate jdbc = new JdbcTemplate(dataSource);
            jdbc.setQueryTimeout(3);

            List<Map<String, Object>> rows = jdbc.queryForList(QUERY_SQL, config.getDictType());
            Map<Integer, String> codeToName = new LinkedHashMap<>();
            for (Map<String, Object> row : rows) {
                String value = row.get("dict_value") == null ? null : String.valueOf(row.get("dict_value"));
                String label = row.get("dict_label") == null ? null : String.valueOf(row.get("dict_label"));
                if (value == null || label == null || value.trim().isEmpty() || label.trim().isEmpty()) {
                    continue;
                }
                try {
                    int code = Integer.parseInt(value.trim());
                    codeToName.put(code, label.trim());
                } catch (NumberFormatException e) {
                    log.warn("[V3车牌] 忽略非数字颜色码: value={}, label={}", value, label);
                }
            }

            if (codeToName.isEmpty()) {
                log.error("[V3车牌] plate_color 字典为空，保留旧快照（当前 {} 个码）",
                        snapshot.codeToName.size());
                return;
            }

            Snapshot next = buildSnapshot(codeToName);
            snapshot = next;
            log.info("[V3车牌] plate_color 字典已加载: type={}, entries={}, codeToName={}",
                    config.getDictType(), next.codeToName.size(), next.codeToName);
        } catch (Exception e) {
            log.error("[V3车牌] plate_color 字典加载失败，保留旧快照（当前 {} 个码）: {}",
                    snapshot.codeToName.size(), e.getMessage());
        } finally {
            refreshing.set(false);
        }
    }

    /** 颜色码是否合法（0 的合法性同样来自字典，不再硬编码） */
    public boolean isValidCode(int code) {
        return snapshot.codeToName.containsKey(code);
    }

    /** 旧格式颜色词 -> 枚举码；无映射返回 -1 */
    public int codeForWord(String word) {
        if (word == null) {
            return -1;
        }
        Integer code = snapshot.wordToCode.get(word);
        return code == null ? -1 : code;
    }

    /** 匹配车牌末尾的颜色词（按长度倒序，最长匹配优先）；无匹配返回 null */
    public String matchSuffix(String normalizedPlate) {
        if (normalizedPlate == null || normalizedPlate.isEmpty()) {
            return null;
        }
        for (String alias : snapshot.aliases) {
            if (normalizedPlate.endsWith(alias)) {
                return alias;
            }
        }
        return null;
    }

    /** 颜色码 -> 字典名称；未知返回“未知” */
    public String displayName(int code) {
        if (code < 0) {
            return "未知";
        }
        String name = snapshot.codeToName.get(code);
        return name == null ? "未知" : name;
    }

    /**
     * 导出展示名：合法码用字典名称；未知码保留原码提示，如“未知(99)”；空值“未知”。
     */
    public String displayName(int code, String rawColor) {
        if (code >= 0) {
            String name = snapshot.codeToName.get(code);
            return name == null ? "未知" : name;
        }
        if (rawColor == null || rawColor.trim().isEmpty()) {
            return "未知";
        }
        return "未知(" + rawColor.trim() + ")";
    }

    public boolean isLoaded() {
        return !snapshot.codeToName.isEmpty();
    }

    public Map<Integer, String> getCodeToName() {
        return snapshot.codeToName;
    }

    private Snapshot buildSnapshot(Map<Integer, String> codeToName) {
        Map<String, Integer> wordToCode = new LinkedHashMap<>();
        List<String> aliases = new ArrayList<>();
        for (Map.Entry<Integer, String> entry : codeToName.entrySet()) {
            String label = entry.getValue();
            addAlias(wordToCode, aliases, label, entry.getKey());

            String withoutSuffix = label.endsWith("底黑字")
                    ? label.substring(0, label.length() - "底黑字".length()).trim()
                    : label;
            if (!withoutSuffix.isEmpty()) {
                addAlias(wordToCode, aliases, withoutSuffix, entry.getKey());
            }
            if (withoutSuffix.endsWith("色") && withoutSuffix.length() > 1) {
                addAlias(wordToCode, aliases, withoutSuffix.substring(0, withoutSuffix.length() - 1),
                        entry.getKey());
            }
            // “黄绿双拼底黑字”额外兼容常见简写“黄绿”
            if (label.contains("黄绿")) {
                addAlias(wordToCode, aliases, "黄绿", entry.getKey());
            }
        }
        aliases.sort(Comparator.comparingInt(String::length).reversed());
        return new Snapshot(codeToName, wordToCode, aliases);
    }

    private void addAlias(Map<String, Integer> wordToCode, List<String> aliases,
                          String alias, int code) {
        if (alias == null || alias.trim().isEmpty()) {
            return;
        }
        String key = alias.trim();
        if (!wordToCode.containsKey(key)) {
            wordToCode.put(key, code);
            aliases.add(key);
        }
    }

    private static class Snapshot {
        private final Map<Integer, String> codeToName;
        private final Map<String, Integer> wordToCode;
        private final List<String> aliases;

        private Snapshot(Map<Integer, String> codeToName,
                         Map<String, Integer> wordToCode,
                         List<String> aliases) {
            this.codeToName = Collections.unmodifiableMap(new LinkedHashMap<>(codeToName));
            this.wordToCode = Collections.unmodifiableMap(new LinkedHashMap<>(wordToCode));
            this.aliases = Collections.unmodifiableList(new ArrayList<>(aliases));
        }

        private static Snapshot empty() {
            return new Snapshot(Collections.<Integer, String>emptyMap(),
                    Collections.<String, Integer>emptyMap(),
                    Collections.<String>emptyList());
        }
    }
}
