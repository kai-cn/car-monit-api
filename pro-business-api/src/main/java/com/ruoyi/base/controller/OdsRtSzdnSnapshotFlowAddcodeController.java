package com.ruoyi.base.controller;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
import com.ruoyi.base.service.v3.query.TrafficListFacade;
import com.ruoyi.base.service.v3.query.TrafficQueryEngineService;
import com.ruoyi.base.service.v3.query.TrafficQueryException;
import com.ruoyi.base.service.v3.query.TrafficSearchResult;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.page.PageDomain;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.core.page.TableSupport;
import com.ruoyi.common.core.redis.RedisCache;
import com.ruoyi.common.utils.CommonUtil;
import com.ruoyi.common.utils.DateUtils;
import com.ruoyi.common.utils.StringUtils;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 门架抓拍流水Controller
 *
 * <p>V3 阶段一：默认 legacy（安全默认），显式配置 {@code traffic.query.engine=es}
 * 且启动就绪检测通过后走 ES（时间范围 + 维度编码 term + 车牌 ngram）；
 * 若 ES/读别名不可用自动回退 legacy 并 WARN。模糊条件在 ES 不可用时返回 503，
 * 禁止回退 GaussDB LIKE（设计 §7 R9）。</p>
 */
@Slf4j
@RestController
@RequestMapping("/base/snapshotflow")
public class OdsRtSzdnSnapshotFlowAddcodeController extends BaseController {

    @Autowired
    private IOdsRtSzdnSnapshotFlowAddcodeService odsRtSzdnSnapshotFlowAddcodeService;

    @Autowired
    private RedisCache redisCache;

    @Autowired
    private TrafficListFacade trafficListFacade;

    @Autowired
    private TrafficQueryEngineService queryEngineService;

    /**
     * 查询门架抓拍流水列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsRtSzdnSnapshotFlowAddcode odsRtSzdnSnapshotFlowAddcode) {
        PageDomain page = TableSupport.buildPageRequest();
        int pageNum = page.getPageNum() == null ? 1 : page.getPageNum();
        int pageSize = page.getPageSize() == null ? 10 : page.getPageSize();

        if (!queryEngineService.isEsActive()) {
            return listLegacy(odsRtSzdnSnapshotFlowAddcode);
        }
        return listFromEs(odsRtSzdnSnapshotFlowAddcode, pageNum, pageSize);
    }

    // ============================================================
    // V3：ES 主路径
    // ============================================================

    private TableDataInfo listFromEs(OdsRtSzdnSnapshotFlowAddcode query, int pageNum, int pageSize) {
        applyDataScope(query);
        try {
            TrafficSearchResult result = trafficListFacade.querySnapshot(query, pageNum, pageSize);
            List<OdsRtSzdnSnapshotFlowAddcode> list = toDomains(result);
            decorate(list);

            TableDataInfo rsp = new TableDataInfo();
            rsp.setCode(200);
            rsp.setMsg("查询成功");
            rsp.setRows(list);
            rsp.setTotal(result.getTotal());
            return rsp;
        } catch (TrafficQueryException e) {
            return errorResult(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("[抓拍列表-V3] 查询异常", e);
            return errorResult(500, "查询失败: " + e.getMessage());
        }
    }

    private void applyDataScope(OdsRtSzdnSnapshotFlowAddcode query) {
        String queryQx = "noall";
        String dataQuery = CommonUtil.isNull(redisCache.getCacheObject("sys_config:data_query"));
        if (CommonUtil.isNotBlank(dataQuery)) {
            queryQx = dataQuery;
        }
        if (!queryQx.equals("queryall")
                && CommonUtil.isBlank(query.getPlatenumber())) {
            query.setFlag("JiAnDong");
        }
    }

    private List<OdsRtSzdnSnapshotFlowAddcode> toDomains(TrafficSearchResult result) {
        List<OdsRtSzdnSnapshotFlowAddcode> list = new ArrayList<>();
        for (Map<String, Object> row : result.getRows()) {
            OdsRtSzdnSnapshotFlowAddcode item = JSON.parseObject(
                    JSON.toJSONString(row), OdsRtSzdnSnapshotFlowAddcode.class);
            // ES 日期存 epoch millis；fastjson2 未转换时兜底
            Object millis = row.get("snapshottime");
            if (item.getSnapshottime() == null && millis instanceof Number) {
                item.setSnapshottime(new Date(((Number) millis).longValue()));
            }
            list.add(item);
        }
        return list;
    }

    private void decorate(List<OdsRtSzdnSnapshotFlowAddcode> list) {
        for (OdsRtSzdnSnapshotFlowAddcode rtn : list) {
            if (rtn == null) {
                // MyBatis 对「所有映射列均为 NULL」的结果行会返回 null 元素（默认语义），
                // 这里显式跳过，避免整页 500；如长期出现需排查数据源侧的脏行。
                log.warn("[抓拍列表] 结果集中存在全列 NULL 的行，已跳过");
                continue;
            }
            rtn.setId(StringUtils.getUUID());
            if (null != rtn.getSnapshottime()) {
                rtn.setSnapshottimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, rtn.getSnapshottime()));
            }
            String imagesArry = CommonUtil.deleteEnd(rtn.getSnappicturepath());
            rtn.setSnappicturepath(CommonUtil.repalacePicUrl(imagesArry));
        }
    }

    private TableDataInfo errorResult(int code, String message) {
        TableDataInfo rsp = new TableDataInfo();
        rsp.setCode(code);
        rsp.setMsg(message);
        rsp.setRows(new ArrayList<>());
        rsp.setTotal(0);
        return rsp;
    }

    // ============================================================
    // 旧路径（配置回退时使用）
    // ============================================================

    private TableDataInfo listLegacy(OdsRtSzdnSnapshotFlowAddcode odsRtSzdnSnapshotFlowAddcode) {
        startPage();

        String queryQx = "noall";
        String dataQuery = CommonUtil.isNull(redisCache.getCacheObject("sys_config:data_query")); // 查询范围
        if (CommonUtil.isNotBlank(dataQuery)) {
            queryQx = dataQuery;
        }

        if (!queryQx.equals("queryall")) {
            String platenumber = odsRtSzdnSnapshotFlowAddcode.getPlatenumber();
            if (CommonUtil.isBlank(platenumber)) {
                odsRtSzdnSnapshotFlowAddcode.setFlag("JiAnDong");
            }
        }

        // 路段
        String sectionCodeStr = odsRtSzdnSnapshotFlowAddcode.getSectionCodeStr();
        if (CommonUtil.isNotBlank(sectionCodeStr)) {
            odsRtSzdnSnapshotFlowAddcode.setSectionList(
                    Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList()));
            odsRtSzdnSnapshotFlowAddcode.setSectioncode("");
        }

        // 门架
        String code = CommonUtil.deleteEnd(odsRtSzdnSnapshotFlowAddcode.getCode());
        if (CommonUtil.isNotBlank(code)) {
            odsRtSzdnSnapshotFlowAddcode.setCodeList(
                    Arrays.stream(code.split(",")).collect(Collectors.toList()));
            odsRtSzdnSnapshotFlowAddcode.setCode("");
        }

        List<OdsRtSzdnSnapshotFlowAddcode> list =
                odsRtSzdnSnapshotFlowAddcodeService
                        .selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode);
        decorate(list);
        return getDataTable(list);
    }

    @GetMapping("/listToExport")
    public List<OdsRtSzdnSnapshotFlowAddcode> listToExport(OdsRtSzdnSnapshotFlowAddcode odsRtSzdnSnapshotFlowAddcode) {
        startPage();

        String queryQx = "noall";
        String dataQuery = CommonUtil.isNull(redisCache.getCacheObject("sys_config:data_query")); // 查询范围
        if (CommonUtil.isNotBlank(dataQuery)) {
            queryQx = dataQuery;
        }

        if (!queryQx.equals("queryall")) {
            String platenumber = odsRtSzdnSnapshotFlowAddcode.getPlatenumber();
            if (CommonUtil.isBlank(platenumber)) {
                odsRtSzdnSnapshotFlowAddcode.setFlag("JiAnDong");
            }
        }

        // 路段
        String sectionCodeStr = odsRtSzdnSnapshotFlowAddcode.getSectionCodeStr();
        if (CommonUtil.isNotBlank(sectionCodeStr)) {
            odsRtSzdnSnapshotFlowAddcode.setSectionList(
                    Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList()));
            odsRtSzdnSnapshotFlowAddcode.setSectioncode("");
        }

        // 门架
        String code = CommonUtil.deleteEnd(odsRtSzdnSnapshotFlowAddcode.getCode());
        if (CommonUtil.isNotBlank(code)) {
            odsRtSzdnSnapshotFlowAddcode.setCodeList(
                    Arrays.stream(code.split(",")).collect(Collectors.toList()));
            odsRtSzdnSnapshotFlowAddcode.setCode("");
        }

        List<OdsRtSzdnSnapshotFlowAddcode> list =
                odsRtSzdnSnapshotFlowAddcodeService
                        .selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode);
        if (null != list && list.size() > 0) {
            for (OdsRtSzdnSnapshotFlowAddcode rtn : list) {
                rtn.setId(StringUtils.getUUID());
                if (null != rtn.getSnapshottime()) {
                    rtn.setSnapshottimeStr(DateUtils.parseDateToStr(
                            DateUtils.YYYY_MM_DD_HH_MM_SS, rtn.getSnapshottime()));
                }
            }
        }
        return list;
    }

    /**
     * 获取门架抓拍流水详细信息
     */
    @GetMapping(value = "/{bigId}")
    public OdsRtSzdnSnapshotFlowAddcode getInfo(@PathVariable("bigId") String bigId) {
        return odsRtSzdnSnapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeById(bigId);
    }
}
