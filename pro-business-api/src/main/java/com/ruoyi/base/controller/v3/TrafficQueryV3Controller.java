package com.ruoyi.base.controller.v3;

import com.ruoyi.base.service.v3.model.TrafficTable;
import com.ruoyi.base.service.v3.query.TrafficQueryApiRequest;
import com.ruoyi.base.service.v3.query.TrafficQueryException;
import com.ruoyi.base.service.v3.query.TrafficSearchRequest;
import com.ruoyi.base.service.v3.query.TrafficSearchResult;
import com.ruoyi.base.service.v3.query.TrafficSearchService;
import com.ruoyi.base.service.v3.query.TrafficTimeUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * V3 组合查询接口（PIT + search_after）。
 *
 * <p>旧接口已保留 pageNum 兼容；本接口用于深分页/导出游标场景，
 * 不在 ES 故障时回退 GaussDB。</p>
 */
@Slf4j
@RestController
@RequestMapping("/api/v3/traffic")
public class TrafficQueryV3Controller {

    private final TrafficSearchService searchService;

    public TrafficQueryV3Controller(TrafficSearchService searchService) {
        this.searchService = searchService;
    }

    @PostMapping("/list")
    public Map<String, Object> list(@RequestBody TrafficQueryApiRequest api) {
        Map<String, Object> response = new LinkedHashMap<>();
        try {
            TrafficSearchRequest req = new TrafficSearchRequest();
            req.setTable(TrafficTable.fromParam(api.getTable()));
            req.setStartMillis(TrafficTimeUtils.parse(api.getStartTime(), false));
            req.setEndMillis(TrafficTimeUtils.parse(api.getEndTime(), true));
            if (api.getDimensionCodes() != null) {
                req.getDimensionCodes().putAll(api.getDimensionCodes());
            }
            req.setPlate(api.getPlate());
            req.setColorCode(api.getColorCode());
            req.setPageSize(api.getPageSize());
            req.setPageNum(api.getPageNum());
            boolean deep = api.getSearchAfter() != null && !api.getSearchAfter().isEmpty();
            req.setSearchAfter(deep ? api.getSearchAfter() : new ArrayList<>());
            req.setPitId(api.getPitId());
            // P1-4：仅深分页或调用方显式要求时保留 PIT。
            // 普通 from/size 分页请求结束后立即关闭，避免每个请求遗留 2 分钟搜索上下文，
            // 持续 QPS 下打满 max_open_scroll_context（默认 500）。
            req.setKeepPit(deep || api.isKeepPit());
            req.setNeedTotal(!deep && api.isNeedTotal());

            TrafficSearchResult result = searchService.search(req);
            response.put("code", 200);
            response.put("message", "ok");
            response.put("rows", result.getRows());
            response.put("total", result.getTotal());
            response.put("hasMore", result.isHasMore());
            response.put("pitId", result.getPitId());
            response.put("searchAfter", result.getSearchAfter());
            response.put("tookMs", result.getTookMs());
        } catch (TrafficQueryException e) {
            response.put("code", e.getCode());
            response.put("message", e.getMessage());
            response.put("rows", new ArrayList<>());
            response.put("total", 0);
        } catch (Exception e) {
            log.error("[V3查询] 异常", e);
            response.put("code", 500);
            response.put("message", e.getMessage());
            response.put("rows", new ArrayList<>());
            response.put("total", 0);
        }
        return response;
    }
}
