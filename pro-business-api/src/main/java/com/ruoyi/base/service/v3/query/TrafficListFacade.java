package com.ruoyi.base.service.v3.query;

import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.plate.PlateColorDictionary;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.concurrent.TimeUnit;

/**
 * 旧接口 -> V3 查询请求的适配层。
 *
 * <p>保持三个既有接口的入参语义（applyTime1/2、sectionCodeStr、code、flag 等），
 * 把名称/编码参数翻译为 ES terms filter，统一交给 {@link TrafficSearchService}。</p>
 */
@Service
public class TrafficListFacade {

    public static final String JIANDONG_ORG_CODE = "030000011";

    private final TrafficSearchService searchService;
    private final DimensionCodeResolver dimensionResolver;
    private final PlateColorDictionary colorDictionary;

    public TrafficListFacade(TrafficSearchService searchService,
                             DimensionCodeResolver dimensionResolver,
                             PlateColorDictionary colorDictionary) {
        this.searchService = searchService;
        this.dimensionResolver = dimensionResolver;
        this.colorDictionary = colorDictionary;
    }

    /** 门架抓拍列表 */
    public TrafficSearchResult querySnapshot(OdsRtSzdnSnapshotFlowAddcode q, int pageNum, int pageSize) {
        TrafficSearchRequest req = new TrafficSearchRequest();
        req.setTable(TrafficTable.SNAPSHOT);
        req.setStartMillis(TrafficTimeUtils.parse(q.getApplyTime1(), false));
        req.setEndMillis(TrafficTimeUtils.parse(q.getApplyTime2(), true));
        req.setPlate(q.getPlatenumber());
        req.setPageNum(pageNum);
        req.setPageSize(pageSize);
        req.setNeedTotal(true);
        req.setKeepPit(false);

        boolean noMatch = false;
        List<String> sectionCodes = firstNonEmpty(
                q.getSectionList(),
                dimensionResolver.splitCodes(q.getSectionCodeStr()),
                single(q.getSectioncode()));
        if (sectionCodes.isEmpty() && notBlank(q.getSectionname())) {
            sectionCodes = dimensionResolver.resolveSectionCodes(q.getSectionname());
            noMatch = sectionCodes.isEmpty();
        }
        req.addCodes("sectioncode", sectionCodes);

        List<String> gantryCodes = firstNonEmpty(
                q.getCodeList(),
                dimensionResolver.splitCodes(q.getCode()),
                single(q.getGantrycode()));
        if (gantryCodes.isEmpty() && notBlank(q.getGantryname())) {
            gantryCodes = dimensionResolver.resolveGantryCodes(q.getGantryname());
            noMatch = noMatch || gantryCodes.isEmpty();
        }
        req.addCodes("gantrycode", gantryCodes);

        List<String> roadCodes = single(q.getRoadcode());
        if (roadCodes.isEmpty() && notBlank(q.getRoadname())) {
            roadCodes = dimensionResolver.resolveRoadCodes(q.getRoadname());
            noMatch = noMatch || roadCodes.isEmpty();
        }
        req.addCodes("roadcode", roadCodes);

        List<String> tollCodes = single(q.getTollcode());
        if (tollCodes.isEmpty() && notBlank(q.getTollname())) {
            tollCodes = dimensionResolver.resolveTollCodes(q.getTollname());
            noMatch = noMatch || tollCodes.isEmpty();
        }
        req.addCodes("tollcode", tollCodes);

        List<String> orgCodes = single(q.getOrgcode());
        if (orgCodes.isEmpty() && notBlank(q.getOrgname())) {
            orgCodes = dimensionResolver.resolveOrgCodes(q.getOrgname());
            noMatch = noMatch || orgCodes.isEmpty();
        }
        if (orgCodes.isEmpty() && isJiandong(q.getFlag())) {
            orgCodes = Collections.singletonList(JIANDONG_ORG_CODE);
        }
        req.addCodes("orgcode", orgCodes);

        return noMatch ? emptyResult() : searchService.search(req);
    }

    /** 收费流水列表 */
    public TrafficSearchResult queryFee(OdsLwzxsfsjFeeRecords01 q, int pageNum, int pageSize) {
        TrafficSearchRequest req = new TrafficSearchRequest();
        req.setTable(TrafficTable.FEE);
        req.setStartMillis(TrafficTimeUtils.parse(q.getInApplyTime1(), false));
        req.setEndMillis(TrafficTimeUtils.parse(q.getInApplyTime2(), true));
        req.setPlate(q.getVehicleplate());
        req.setPageNum(pageNum);
        req.setPageSize(pageSize);
        req.setNeedTotal(true);
        req.setKeepPit(false);

        // 颜色：数字码直接下发；旧颜色词按码表映射；无法映射则返回空
        boolean noMatch = false;
        String color = resolveColor(q.getPlateColor());
        if (color != null) {
            req.setColorCode(color);
        } else if (notBlank(q.getPlateColor())) {
            noMatch = true;
        }

        List<String> sectionCodes = firstNonEmpty(
                q.getSectionList(),
                dimensionResolver.splitCodes(q.getSectionCodeStr()),
                single(q.getSectioncode()));
        if (sectionCodes.isEmpty() && notBlank(q.getSectionname())) {
            sectionCodes = dimensionResolver.resolveSectionCodes(q.getSectionname());
            noMatch = noMatch || sectionCodes.isEmpty();
        }
        req.addCodes("sectioncode", sectionCodes);

        List<String> gantryCodes = firstNonEmpty(
                q.getCodeList(),
                dimensionResolver.splitCodes(q.getCode()),
                single(q.getGantryid()));
        if (gantryCodes.isEmpty() && notBlank(q.getGantryName())) {
            gantryCodes = dimensionResolver.resolveGantryCodes(q.getGantryName());
            noMatch = noMatch || gantryCodes.isEmpty();
        }
        req.addCodes("gantrycode", gantryCodes);

        List<String> roadCodes = single(q.getRoadcode());
        if (roadCodes.isEmpty() && notBlank(q.getRoadname())) {
            roadCodes = dimensionResolver.resolveRoadCodes(q.getRoadname());
            noMatch = noMatch || roadCodes.isEmpty();
        }
        req.addCodes("roadcode", roadCodes);

        List<String> tollCodes = single(q.getTollcode());
        if (tollCodes.isEmpty() && notBlank(q.getTollname())) {
            tollCodes = dimensionResolver.resolveTollCodes(q.getTollname());
            noMatch = noMatch || tollCodes.isEmpty();
        }
        req.addCodes("tollcode", tollCodes);

        List<String> orgCodes = single(q.getOrgcode());
        if (orgCodes.isEmpty() && notBlank(q.getOrgname())) {
            orgCodes = dimensionResolver.resolveOrgCodes(q.getOrgname());
            noMatch = noMatch || orgCodes.isEmpty();
        }
        if (orgCodes.isEmpty() && isJiandong(q.getFlag())) {
            orgCodes = Collections.singletonList(JIANDONG_ORG_CODE);
        }
        req.addCodes("orgcode", orgCodes);

        return noMatch ? emptyResult() : searchService.search(req);
    }

    /**
     * 轨迹按车牌查询：默认最近半年（与旧接口 flag=bannian 一致）。
     */
    public TrafficSearchResult queryTrail(String carNo, String startTime, String endTime,
                                          int pageNum, int pageSize) {
        if (carNo == null || carNo.trim().isEmpty()) {
            return emptyResult();
        }
        TrafficSearchRequest req = new TrafficSearchRequest();
        req.setTable(TrafficTable.TRAIL);
        Long start = TrafficTimeUtils.parse(startTime, false);
        Long end = TrafficTimeUtils.parse(endTime, true);
        long now = System.currentTimeMillis();
        req.setStartMillis(start != null ? start : now - TimeUnit.DAYS.toMillis(180));
        req.setEndMillis(end != null ? end : now);
        req.setPlate(carNo);
        req.setPageNum(pageNum);
        req.setPageSize(pageSize);
        req.setNeedTotal(true);
        req.setKeepPit(false);
        return searchService.search(req);
    }

    /** V3 接口：PIT + search_after 深分页 */
    public TrafficSearchResult searchAfter(TrafficSearchRequest req) {
        req.setKeepPit(true);
        req.setNeedTotal(false);
        return searchService.search(req);
    }

    private String resolveColor(String raw) {
        if (raw == null || raw.trim().isEmpty()) {
            return null;
        }
        String v = raw.trim();
        if (v.matches("[0-9]{1,3}")) {
            return v;
        }
        int code = colorDictionary.codeForWord(v);
        return code >= 0 ? String.valueOf(code) : null;
    }

    private TrafficSearchResult emptyResult() {
        TrafficSearchResult empty = new TrafficSearchResult();
        empty.setTotal(0);
        empty.setHasMore(false);
        empty.setRows(new ArrayList<>());
        return empty;
    }

    @SafeVarargs
    private final List<String> firstNonEmpty(List<String>... candidates) {
        if (candidates != null) {
            for (List<String> c : candidates) {
                if (c != null && !c.isEmpty()) {
                    return c;
                }
            }
        }
        return Collections.emptyList();
    }

    private List<String> single(String value) {
        return notBlank(value) ? Collections.singletonList(value.trim()) : Collections.emptyList();
    }

    private boolean notBlank(String value) {
        return value != null && !value.trim().isEmpty();
    }

    private boolean isJiandong(String flag) {
        return flag != null && "jiandong".equalsIgnoreCase(flag.trim());
    }
}
