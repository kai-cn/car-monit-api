package com.ruoyi.base.controller;

import com.ruoyi.base.service.optimization.ProgressiveQueryArchitectureService;
import com.ruoyi.base.service.optimization.ProgressiveQueryArchitectureService.QueryRequest;
import com.ruoyi.base.service.optimization.ProgressiveQueryArchitectureService.QueryResult;
import com.ruoyi.base.service.optimization.ProgressiveQueryArchitectureService.DataScaleLevel;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 渐进式查询架构 Controller - Progressive Query Architecture Controller
 * <p>
 * 设计目的 / Design Purpose:
 *   统一对外提供3张核心大表的优化查询入口，根据数据量级别自动选择最优查询策略。
 *   Provides unified optimized query endpoints for 3 core large tables,
 *   automatically selecting the best query strategy based on data volume.
 * <p>
 * 接口说明 / API Description:
 *   1. GET /progressive/snapshotflow/list  - 门架抓拍流水渐进式查询
 *   2. GET /progressive/feerecords/list    - 收费流水渐进式查询
 *   3. GET /progressive/trailfitting/list  - 车辆轨迹渐进式查询
 *   4. GET /progressive/scale-level        - 查看当前数据量级别
 */
@Slf4j
@RestController
@RequestMapping("/progressive")
public class ProgressiveQueryController extends BaseController {

    @Autowired
    private ProgressiveQueryArchitectureService progressiveQueryService;

    /**
     * 门架抓拍流水渐进式查询
     * Progressive query for snapshot flow data
     *
     * @param startTime   开始时间 (format: yyyy-MM-dd HH:mm:ss)
     * @param endTime     结束时间
     * @param platenumber 车牌号（支持模糊查询）
     * @param gantryname  门架名称（支持模糊查询）
     * @param roadname    路线名称（支持模糊查询）
     * @param sectionname 路段名称（支持模糊查询）
     * @param orgname     管理中心名称（支持模糊查询）
     * @param tollname    收费站名称（支持模糊查询）
     * @param cursor      游标（上一页最后一条的 snapshottime，用于游标分页）
     * @param pageSize    每页大小
     */
    @GetMapping("/snapshotflow/list")
    public TableDataInfo snapshotFlowList(
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            @RequestParam(required = false) String platenumber,
            @RequestParam(required = false) String gantryname,
            @RequestParam(required = false) String roadname,
            @RequestParam(required = false) String sectionname,
            @RequestParam(required = false) String orgname,
            @RequestParam(required = false) String tollname,
            @RequestParam(required = false) String cursor,
            @RequestParam(defaultValue = "20") int pageSize) {

        // 构建统一查询请求 / Build unified query request
        QueryRequest request = new QueryRequest();
        request.setStartTime(startTime);
        request.setEndTime(endTime);
        request.setPlatenumber(platenumber);
        request.setGantryname(gantryname);
        request.setRoadname(roadname);
        request.setSectionname(sectionname);
        request.setOrgname(orgname);
        request.setTollname(tollname);
        request.setCursor(cursor);
        request.setPageSize(pageSize);

        // 执行渐进式查询 / Execute progressive query
        QueryResult result = progressiveQueryService.querySnapshotFlow(request);

        // 封装分页结果 / Wrap paginated result
        TableDataInfo tableData = getDataTable((List<?>) result.getData());
        tableData.setMsg("策略: " + result.getStrategy());
        return tableData;
    }

    /**
     * 收费流水渐进式查询
     * Progressive query for fee records data
     */
    @GetMapping("/feerecords/list")
    public TableDataInfo feeRecordsList(
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            @RequestParam(required = false) String platenumber,
            @RequestParam(required = false) String gantryname,
            @RequestParam(required = false) String roadname,
            @RequestParam(required = false) String sectionname,
            @RequestParam(required = false) String orgname,
            @RequestParam(required = false) String tollname,
            @RequestParam(required = false) String cursor,
            @RequestParam(defaultValue = "20") int pageSize) {

        QueryRequest request = new QueryRequest();
        request.setStartTime(startTime);
        request.setEndTime(endTime);
        request.setPlatenumber(platenumber);
        request.setGantryname(gantryname);
        request.setRoadname(roadname);
        request.setSectionname(sectionname);
        request.setOrgname(orgname);
        request.setTollname(tollname);
        request.setCursor(cursor);
        request.setPageSize(pageSize);

        QueryResult result = progressiveQueryService.queryFeeRecords(request);

        TableDataInfo tableData = getDataTable((List<?>) result.getData());
        tableData.setMsg("策略: " + result.getStrategy());
        return tableData;
    }

    /**
     * 车辆轨迹渐进式查询
     * Progressive query for trail fitting data
     */
    @GetMapping("/trailfitting/list")
    public TableDataInfo trailFittingList(
            @RequestParam(required = false) String startTime,
            @RequestParam(required = false) String endTime,
            @RequestParam(required = false) String platenumber,
            @RequestParam(required = false) String gantryname,
            @RequestParam(required = false) String roadname,
            @RequestParam(required = false) String sectionname,
            @RequestParam(required = false) String orgname,
            @RequestParam(required = false) String tollname,
            @RequestParam(required = false) String cursor,
            @RequestParam(defaultValue = "20") int pageSize) {

        QueryRequest request = new QueryRequest();
        request.setStartTime(startTime);
        request.setEndTime(endTime);
        request.setPlatenumber(platenumber);
        request.setGantryname(gantryname);
        request.setRoadname(roadname);
        request.setSectionname(sectionname);
        request.setOrgname(orgname);
        request.setTollname(tollname);
        request.setCursor(cursor);
        request.setPageSize(pageSize);

        QueryResult result = progressiveQueryService.queryTrailFitting(request);

        TableDataInfo tableData = getDataTable((List<?>) result.getData());
        tableData.setMsg("策略: " + result.getStrategy());
        return tableData;
    }

    /**
     * 查看当前数据量级别
     * Check current data scale level for all 3 tables
     */
    @GetMapping("/scale-level")
    public AjaxResult scaleLevel() {
        java.util.Map<String, String> levels = new java.util.LinkedHashMap<>();
        levels.put("ods_rt_szdn_snapshot_flow_addcode",
                progressiveQueryService.detectScaleLevel("ods_rt_szdn_snapshot_flow_addcode").name());
        levels.put("ods_lwzxsfsj_fee_records_01",
                progressiveQueryService.detectScaleLevel("ods_lwzxsfsj_fee_records_01").name());
        levels.put("zdata_trail_fitting",
                progressiveQueryService.detectScaleLevel("zdata_trail_fitting").name());
        return AjaxResult.success(levels);
    }
}
