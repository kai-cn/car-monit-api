package com.ruoyi.base.service.v3.plate;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 车牌解析器（收费真实格式 {@code 赣B21E85_0}）。
 *
 * <p>解析规则对应设计 §5.1.6：</p>
 * <ol>
 *   <li>优先匹配 {@code ^(车牌核心)_([0-9]{1,3})$}，下划线后为颜色枚举码；</li>
 *   <li>车牌核心做去空格/点/分隔符、全角转半角、统一大写，再做车牌正则校验；</li>
 *   <li>颜色码查码表：合法 -> ok；非法 -> color_unparsed + -1；</li>
 *   <li>无颜色后缀 -> no_color + -1；旧格式颜色词按码表映射；</li>
 *   <li>核心校验失败 -> unparsed + 最佳努力核心 + 保留 plate_raw，不丢行。</li>
 * </ol>
 *
 * <p>本类是无状态工具，供查询、同步、导出共用，保证三处解析口径一致。</p>
 */
@Slf4j
@Component
public class PlateNumberParser {

    public static final String STATUS_OK = "ok";
    public static final String STATUS_NO_COLOR = "no_color";
    public static final String STATUS_COLOR_UNPARSED = "color_unparsed";
    public static final String STATUS_UNPARSED = "unparsed";

    /** 省份简称 + 发牌机关字母 + 5/6 位字母数字（新能源 8 位） */
    private static final Pattern CORE_PATTERN = Pattern.compile(
            "^[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领]"
                    + "[A-Z][A-Z0-9]{5,6}$");

    /** 下划线 + 1~3 位数字颜色码 */
    private static final Pattern COLOR_SUFFIX_PATTERN = Pattern.compile("^(.*)_([0-9]{1,3})$");

    private final PlateColorDictionary colorDictionary;

    @Autowired
    public PlateNumberParser(PlateColorDictionary colorDictionary) {
        this.colorDictionary = colorDictionary;
    }

    /**
     * 完整解析原始车牌。
     */
    public PlateParseResult parse(String raw) {
        String plateRaw = raw == null ? null : raw.trim();
        String normalized = normalize(plateRaw);
        if (normalized.isEmpty()) {
            return PlateParseResult.unparsed(plateRaw, "", null);
        }

        // 1) 数字颜色码后缀：赣B21E85_0
        Matcher numeric = COLOR_SUFFIX_PATTERN.matcher(normalized);
        if (numeric.matches()) {
            String coreCandidate = numeric.group(1);
            String colorRaw = numeric.group(2);
            int code = parseIntSafely(colorRaw);
            if (isCoreValid(coreCandidate)) {
                return build(plateRaw, coreCandidate, colorRaw,
                        colorDictionary.isValidCode(code) ? code : -1,
                        colorDictionary.isValidCode(code) ? STATUS_OK : STATUS_COLOR_UNPARSED);
            }
            return PlateParseResult.unparsed(plateRaw, bestEffortCore(coreCandidate), colorRaw);
        }

        // 2) 旧格式颜色词后缀（颜色词来自 dict_plate_color，不再硬编码）
        String colorWord = colorDictionary.matchSuffix(normalized);
        if (colorWord != null) {
            String coreCandidate = normalized.substring(0, normalized.length() - colorWord.length());
            if (isCoreValid(coreCandidate)) {
                int code = colorDictionary.codeForWord(colorWord);
                return build(plateRaw, coreCandidate, colorWord, code,
                        code >= 0 ? STATUS_OK : STATUS_COLOR_UNPARSED);
            }
            return PlateParseResult.unparsed(plateRaw, bestEffortCore(coreCandidate), colorWord);
        }

        // 3) 畸形下划线：赣B21E85_0_extra -> 核心最佳努力，颜色原码保留，状态 unparsed
        int underscore = normalized.indexOf('_');
        if (underscore >= 0) {
            String coreCandidate = normalized.substring(0, underscore);
            String colorRaw = normalized.substring(underscore + 1);
            return PlateParseResult.unparsed(plateRaw, bestEffortCore(coreCandidate), colorRaw);
        }

        // 4) 无颜色：赣B21E85
        if (isCoreValid(normalized)) {
            return build(plateRaw, normalized, null, -1, STATUS_NO_COLOR);
        }

        // 5) 无法识别：保留原值兜底
        return PlateParseResult.unparsed(plateRaw, bestEffortCore(normalized), null);
    }

    /**
     * 归一化车牌核心（供 ES plate_norm 使用）。解析失败时返回“尽量去掉颜色后缀”的值，
     * 保证按片段模糊仍可命中（设计 §5.1.6“解析失败/颜色未知的入库与检索”）。
     */
    public String normalizeForIndex(String raw) {
        PlateParseResult result = parse(raw);
        if (result.getPlateCore() == null || result.getPlateCore().isEmpty()) {
            return normalize(raw);
        }
        return result.getPlateCore();
    }

    /**
     * 是否为完整车牌（7~8 位）；用于决定 term 精确查询还是 ngram 模糊查询。
     */
    public boolean isFullPlate(String normalizedCore) {
        if (normalizedCore == null) {
            return false;
        }
        return normalizedCore.length() >= 7 && normalizedCore.length() <= 8;
    }

    /**
     * 规范化：全角转半角、去空格/点/分隔符、统一大写。
     * 注意保留下划线，它是颜色码分隔符。
     */
    public String normalize(String raw) {
        if (raw == null) {
            return "";
        }
        String trimmed = raw.trim();
        StringBuilder sb = new StringBuilder(trimmed.length());
        for (int i = 0; i < trimmed.length(); i++) {
            char c = trimmed.charAt(i);
            if (c == '\u3000') {
                continue;
            }
            if (c >= '\uFF01' && c <= '\uFF5E') {
                c = (char) (c - 0xFEE0);
            }
            if (c == ' ' || c == '\t' || c == '.' || c == '·' || c == '-' || c == '—') {
                continue;
            }
            sb.append(c);
        }
        return sb.toString().toUpperCase(Locale.ROOT);
    }

    private PlateParseResult build(String raw, String core, String colorRaw, int code, String status) {
        PlateParseResult r = new PlateParseResult();
        r.setPlateRaw(raw);
        r.setPlateCore(core);
        r.setPlateColorRaw(colorRaw);
        r.setPlateColorCode(code);
        r.setPlateParseStatus(status);
        r.setPlateColorName(colorDictionary.displayName(code, colorRaw));
        return r;
    }

    private boolean isCoreValid(String core) {
        return core != null && !core.isEmpty() && CORE_PATTERN.matcher(core).matches();
    }

    private String bestEffortCore(String candidate) {
        String normalized = normalize(candidate);
        if (isCoreValid(normalized)) {
            return normalized;
        }
        // 常见脏值：尾部残留颜色码/多余字符；尽量保留可检索片段
        int underscore = normalized.indexOf('_');
        if (underscore > 0) {
            normalized = normalized.substring(0, underscore);
        }
        return normalized;
    }

    private int parseIntSafely(String value) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return -1;
        }
    }

    /** 供少量本地验证使用：按输入返回解析结果的可读串 */
    public String describe(String raw) {
        PlateParseResult r = parse(raw);
        return "plate_core=" + r.getPlateCore()
                + ", plate_color_code=" + r.getPlateColorCode()
                + ", plate_color_name=" + r.getPlateColorName()
                + ", plate_color_raw=" + r.getPlateColorRaw()
                + ", plate_raw=" + r.getPlateRaw()
                + ", status=" + r.getPlateParseStatus();
    }
}
