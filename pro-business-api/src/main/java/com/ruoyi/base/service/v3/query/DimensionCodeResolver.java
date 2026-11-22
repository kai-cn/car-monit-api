package com.ruoyi.base.service.v3.query;

import com.ruoyi.base.domain.OdsSzdnGantry;
import com.ruoyi.base.domain.OdsSzdnSection;
import com.ruoyi.base.domain.OdsSzdnToll;
import com.ruoyi.base.domain.OdsYhglVBaseOrg;
import com.ruoyi.base.service.IOdsSzdnGantryService;
import com.ruoyi.base.service.IOdsSzdnSectionService;
import com.ruoyi.base.service.IOdsSzdnTollService;
import com.ruoyi.base.service.IOdsYhglVBaseOrgService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 维度名称 -> 编码解析（设计 §5.1.4）。
 *
 * <p>事实表不为名称字段建 ngram：查询入口先在小码表做 contains/等值匹配，
 * 得到编码列表后作为 ES terms filter 下推。码表不完整时返回空列表，
 * 由调用方返回空结果（默认拒绝），绝不回退到事实表全模糊。</p>
 */
@Slf4j
@Service
public class DimensionCodeResolver {

    private static final long CACHE_TTL_MS = 10 * 60 * 1000L;

    private final IOdsYhglVBaseOrgService orgService;
    private final IOdsSzdnSectionService sectionService;
    private final IOdsSzdnGantryService gantryService;
    private final IOdsSzdnTollService tollService;

    private volatile Cache<List<OdsYhglVBaseOrg>> orgCache;
    private volatile Cache<List<OdsSzdnSection>> sectionCache;
    private volatile Cache<List<OdsSzdnGantry>> gantryCache;
    private volatile Cache<List<OdsSzdnToll>> tollCache;

    public DimensionCodeResolver(IOdsYhglVBaseOrgService orgService,
                                 IOdsSzdnSectionService sectionService,
                                 IOdsSzdnGantryService gantryService,
                                 IOdsSzdnTollService tollService) {
        this.orgService = orgService;
        this.sectionService = sectionService;
        this.gantryService = gantryService;
        this.tollService = tollService;
    }

    public List<String> resolveOrgCodes(String value) {
        if (value == null || value.trim().isEmpty()) {
            return Collections.emptyList();
        }
        List<OdsYhglVBaseOrg> list = orgCache == null ? null : orgCache.value;
        if (list == null || orgCache.expired()) {
            try {
                list = orgService.list();
            } catch (Exception e) {
                log.warn("[V3维度] 机构码表加载失败: {}", e.getMessage());
                list = Collections.emptyList();
            }
            if (list == null) {
                list = Collections.emptyList();
            }
            orgCache = new Cache<>(list, System.currentTimeMillis() + CACHE_TTL_MS);
        }
        String q = normalize(value);
        return list.stream()
                .filter(o -> contains(o.getOrgName(), q) || equalsCode(o.getOrgCode(), q))
                .map(OdsYhglVBaseOrg::getOrgCode)
                .filter(this::notBlank)
                .distinct()
                .collect(Collectors.toList());
    }

    public List<String> resolveSectionCodes(String value) {
        if (value == null || value.trim().isEmpty()) {
            return Collections.emptyList();
        }
        List<OdsSzdnSection> list = sectionCache == null ? null : sectionCache.value;
        if (list == null || sectionCache.expired()) {
            try {
                list = sectionService.getSectionList();
            } catch (Exception e) {
                log.warn("[V3维度] 路段码表加载失败: {}", e.getMessage());
                list = Collections.emptyList();
            }
            sectionCache = new Cache<>(list == null ? Collections.emptyList() : list,
                    System.currentTimeMillis() + CACHE_TTL_MS);
        }
        if (list == null) {
            list = Collections.emptyList();
        }
        String q = normalize(value);
        return list.stream()
                .filter(s -> contains(s.getSectionName(), q) || equalsCode(s.getSectionCode(), q))
                .map(OdsSzdnSection::getSectionCode)
                .filter(this::notBlank)
                .distinct()
                .collect(Collectors.toList());
    }

    public List<String> resolveGantryCodes(String value) {
        if (value == null || value.trim().isEmpty()) {
            return Collections.emptyList();
        }
        List<OdsSzdnGantry> list = loadGantries();
        String q = normalize(value);
        return list.stream()
                .filter(g -> contains(g.getGantryName(), q) || equalsCode(g.getGantryCode(), q))
                .map(OdsSzdnGantry::getGantryCode)
                .filter(this::notBlank)
                .distinct()
                .collect(Collectors.toList());
    }

    private List<OdsSzdnGantry> loadGantries() {
        List<OdsSzdnGantry> list = gantryCache == null ? null : gantryCache.value;
        if (list == null || gantryCache.expired()) {
            try {
                list = gantryService.getGantryRedis();
            } catch (Exception e) {
                log.warn("[V3维度] 门架码表加载失败: {}", e.getMessage());
                list = Collections.emptyList();
            }
            gantryCache = new Cache<>(list == null ? Collections.emptyList() : list,
                    System.currentTimeMillis() + CACHE_TTL_MS);
        }
        return list == null ? Collections.emptyList() : list;
    }

    /**
     * 收费表维度下推修正（P1-1/P1-2）。
     *
     * <p>收费事实表只有 {@code gantryid}，没有 {@code orgcode/roadcode/tollcode}
     * 物理列，ES 文档也不写这三列。若把 org/road/toll 编码直接下推为 terms，
     * {@code dynamic: strict} 下会静默命中 0 条。这里改为经门架码表把这三个维度
     * 翻译成门架编码集合，再按 {@code gantrycode}（收费表映射到 gantryid）过滤。</p>
     *
     * <p>直接就地修改 {@code codes}：移除 orgcode/roadcode/tollcode；
     * {@code sectioncode} 保留（回灌 SQL 已补该列，可直接过滤）。</p>
     *
     * @return false 表示维度组合在码表中无匹配，调用方应直接返回空结果
     */
    public boolean translateFeeDimensions(Map<String, List<String>> codes) {
        if (codes == null || codes.isEmpty()) {
            return true;
        }
        List<String> org = codes.remove("orgcode");
        List<String> road = codes.remove("roadcode");
        List<String> toll = codes.remove("tollcode");
        if (isEmpty(org) && isEmpty(road) && isEmpty(toll)) {
            return true;
        }

        List<String> derived = loadGantries().stream()
                .filter(g -> matchCode(g.getOrgCode(), org)
                        && matchCode(g.getRoadCode(), road)
                        && matchCode(g.getTollCode(), toll))
                .map(OdsSzdnGantry::getGantryCode)
                .filter(this::notBlank)
                .distinct()
                .collect(Collectors.toList());
        if (derived.isEmpty()) {
            return false;
        }

        List<String> explicit = codes.get("gantrycode");
        if (!isEmpty(explicit)) {
            List<String> intersect = explicit.stream()
                    .filter(v -> containsCodeIgnoreCase(derived, v))
                    .collect(Collectors.toList());
            if (intersect.isEmpty()) {
                return false;
            }
            codes.put("gantrycode", intersect);
        } else {
            codes.put("gantrycode", derived);
        }
        return true;
    }

    private boolean isEmpty(List<String> values) {
        return values == null || values.isEmpty();
    }

    /** 维度未指定时视为匹配；指定时按编码大小写不敏感匹配。 */
    private boolean matchCode(String code, List<String> values) {
        if (isEmpty(values)) {
            return true;
        }
        if (code == null) {
            return false;
        }
        for (String value : values) {
            if (value != null && code.trim().equalsIgnoreCase(value.trim())) {
                return true;
            }
        }
        return false;
    }

    private boolean containsCodeIgnoreCase(List<String> codes, String value) {
        if (value == null) {
            return false;
        }
        for (String code : codes) {
            if (code != null && code.trim().equalsIgnoreCase(value.trim())) {
                return true;
            }
        }
        return false;
    }

    public List<String> resolveRoadCodes(String value) {
        if (value == null || value.trim().isEmpty()) {
            return Collections.emptyList();
        }
        List<OdsSzdnSection> list = sectionCache == null ? null : sectionCache.value;
        if (list == null || sectionCache.expired()) {
            try {
                list = sectionService.getSectionList();
            } catch (Exception e) {
                log.warn("[V3维度] 路段码表加载失败: {}", e.getMessage());
                list = Collections.emptyList();
            }
            sectionCache = new Cache<>(list == null ? Collections.emptyList() : list,
                    System.currentTimeMillis() + CACHE_TTL_MS);
        }
        if (list == null) {
            list = Collections.emptyList();
        }
        String q = normalize(value);
        return list.stream()
                .filter(s -> contains(s.getRoadName(), q) || equalsCode(s.getRoadCode(), q))
                .map(OdsSzdnSection::getRoadCode)
                .filter(this::notBlank)
                .distinct()
                .collect(Collectors.toList());
    }

    public List<String> resolveTollCodes(String value) {
        if (value == null || value.trim().isEmpty()) {
            return Collections.emptyList();
        }
        List<OdsSzdnToll> list = tollCache == null ? null : tollCache.value;
        if (list == null || tollCache.expired()) {
            try {
                list = new ArrayList<>(tollService.getRedisMap().values());
            } catch (Exception e) {
                log.warn("[V3维度] 收费站码表加载失败: {}", e.getMessage());
                list = Collections.emptyList();
            }
            tollCache = new Cache<>(list == null ? Collections.emptyList() : list,
                    System.currentTimeMillis() + CACHE_TTL_MS);
        }
        if (list == null) {
            list = Collections.emptyList();
        }
        String q = normalize(value);
        return list.stream()
                .filter(t -> contains(t.getTollName(), q) || equalsCode(t.getTollCode(), q))
                .map(OdsSzdnToll::getTollCode)
                .filter(this::notBlank)
                .distinct()
                .collect(Collectors.toList());
    }

    /** 逗号分隔编码串 -> 列表（用于 sectionCodeStr/code 参数） */
    public List<String> splitCodes(String codeStr) {
        if (codeStr == null || codeStr.trim().isEmpty()) {
            return Collections.emptyList();
        }
        return java.util.Arrays.stream(codeStr.split(","))
                .map(String::trim)
                .filter(s -> !s.isEmpty())
                .distinct()
                .collect(Collectors.toList());
    }

    private boolean notBlank(String s) {
        return s != null && !s.trim().isEmpty();
    }

    private boolean contains(String name, String query) {
        return name != null && name.toLowerCase(Locale.ROOT).contains(query);
    }

    private boolean equalsCode(String code, String query) {
        return code != null && code.toLowerCase(Locale.ROOT).equals(query);
    }

    private String normalize(String value) {
        return value.trim().toLowerCase(Locale.ROOT);
    }

    private static class Cache<T> {
        private final T value;
        private final long expireAt;

        private Cache(T value, long expireAt) {
            this.value = value;
            this.expireAt = expireAt;
        }

        private boolean expired() {
            return System.currentTimeMillis() > expireAt;
        }
    }
}
