package com.ruoyi.base.controller;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.domain.OdsSzdnGantry;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service;
import com.ruoyi.base.service.IOdsSzdnGantryService;
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
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.Date;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 基础-收费流水Controller
 *
 * <p>V3 阶段一：默认 legacy；显式配置 {@code traffic.query.engine=es} 且启动就绪检测通过后走 ES；
 * 车牌拆 plate_core + plate_color_code，颜色作为可选 term；
 * ES 不可用时返回 503，禁止回退 GaussDB 全模糊。</p>
 */
@Slf4j
@RestController
@RequestMapping("/base/feerecords")
public class OdsLwzxsfsjFeeRecords01Controller extends BaseController {

    @Autowired
    private IOdsLwzxsfsjFeeRecords01Service odsLwzxsfsjFeeRecords01Service;

    @Autowired
    private IOdsSzdnGantryService odsSzdnGantryService;

    @Autowired
    private RedisCache redisCache;

    @Autowired
    private TrafficListFacade trafficListFacade;

    @Autowired
    private TrafficQueryEngineService queryEngineService;

    /**
     * 查询基础-收费流水列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01) {
        PageDomain page = TableSupport.buildPageRequest();
        int pageNum = page.getPageNum() == null ? 1 : page.getPageNum();
        int pageSize = page.getPageSize() == null ? 10 : page.getPageSize();

        if (!queryEngineService.isEsActive()) {
            return listLegacy(odsLwzxsfsjFeeRecords01);
        }
        return listFromEs(odsLwzxsfsjFeeRecords01, pageNum, pageSize);
    }

    // ============================================================
    // V3：ES 主路径
    // ============================================================

    private TableDataInfo listFromEs(OdsLwzxsfsjFeeRecords01 query, int pageNum, int pageSize) {
        applyDataScope(query);
        try {
            TrafficSearchResult result = trafficListFacade.queryFee(query, pageNum, pageSize);
            List<OdsLwzxsfsjFeeRecords01> list = toDomains(result);

            TableDataInfo rsp = new TableDataInfo();
            rsp.setCode(200);
            rsp.setMsg("查询成功");
            rsp.setRows(list);
            rsp.setTotal(result.getTotal());
            return rsp;
        } catch (TrafficQueryException e) {
            return errorResult(e.getCode(), e.getMessage());
        } catch (Exception e) {
            log.error("[收费列表-V3] 查询异常", e);
            return errorResult(500, "查询失败: " + e.getMessage());
        }
    }

    private void applyDataScope(OdsLwzxsfsjFeeRecords01 query) {
        String queryQx = "noall";
        String dataQuery = CommonUtil.isNull(redisCache.getCacheObject("sys_config:data_query"));
        if (CommonUtil.isNotBlank(dataQuery)) {
            queryQx = dataQuery;
        }
        if (!queryQx.equals("queryall") && CommonUtil.isBlank(query.getVehicleplate())) {
            query.setFlag("JiAnDong");
        }
    }

    private List<OdsLwzxsfsjFeeRecords01> toDomains(TrafficSearchResult result) {
        List<OdsLwzxsfsjFeeRecords01> list = new ArrayList<>();
        for (Map<String, Object> row : result.getRows()) {
            OdsLwzxsfsjFeeRecords01 fee = JSON.parseObject(
                    JSON.toJSONString(row), OdsLwzxsfsjFeeRecords01.class);
            if (fee.getTranstime() == null && row.get("transtime") instanceof Number) {
                fee.setTranstime(new Date(((Number) row.get("transtime")).longValue()));
            }
            if (fee.getLastgantrytime() == null && row.get("lastgantrytime") instanceof Number) {
                fee.setLastgantrytime(new Date(((Number) row.get("lastgantrytime")).longValue()));
            }

            // 兼容旧响应：车牌去颜色后缀；门架名称/路段编码来自 ES 展示字段
            String vehicleplate = CommonUtil.isNull(fee.getVehicleplate());
            if (vehicleplate.indexOf("_") > -1) {
                fee.setVehicleplate(vehicleplate.split("_")[0]);
            }
            if (fee.getGantryName() == null || fee.getGantryName().trim().isEmpty()) {
                Object gantryName = row.get("gantryname");
                if (gantryName != null) {
                    fee.setGantryName(String.valueOf(gantryName));
                }
            }
            if ((fee.getSectionCodeStr() == null || fee.getSectionCodeStr().trim().isEmpty())
                    && row.get("sectioncode") != null) {
                fee.setSectionCodeStr(String.valueOf(row.get("sectioncode")));
            }
            if (null != fee.getTranstime()) {
                fee.setTranstimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, fee.getTranstime()));
            }
            if (null != fee.getLastgantrytime()) {
                fee.setLastgantrytimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, fee.getLastgantrytime()));
            }
            list.add(fee);
        }
        return list;
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

    private TableDataInfo listLegacy(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01) {
        startPage();

        String queryQx = "noall";
        String dataQuery = CommonUtil.isNull(redisCache.getCacheObject("sys_config:data_query"));
        if (CommonUtil.isNotBlank(dataQuery)) {
            queryQx = dataQuery;
        }

        if (!queryQx.equals("queryall")) {
            String vehicleplateQuery = odsLwzxsfsjFeeRecords01.getVehicleplate();
            if (CommonUtil.isBlank(vehicleplateQuery)) {
                odsLwzxsfsjFeeRecords01.setFlag("JiAnDong");
            }
        }

        // 路段
        String sectionCodeStr = odsLwzxsfsjFeeRecords01.getSectionCodeStr();
        if (CommonUtil.isNotBlank(sectionCodeStr)) {
            odsLwzxsfsjFeeRecords01.setSectionList(
                    Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList()));
        }

        // 门架
        String code = CommonUtil.deleteEnd(odsLwzxsfsjFeeRecords01.getCode());
        if (CommonUtil.isNotBlank(code)) {
            odsLwzxsfsjFeeRecords01.setCodeList(
                    Arrays.stream(code.split(",")).collect(Collectors.toList()));
            odsLwzxsfsjFeeRecords01.setCode("");
        }

        List<OdsLwzxsfsjFeeRecords01> list =
                odsLwzxsfsjFeeRecords01Service
                        .selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01);
        decorateLegacy(list);
        return getDataTable(list);
    }

    private void decorateLegacy(List<OdsLwzxsfsjFeeRecords01> list) {
        if (list == null || list.isEmpty()) {
            return;
        }
        List<OdsSzdnGantry> gantryList = odsSzdnGantryService.getGantryRedis();
        Map<String, OdsSzdnGantry> gantryMap = new HashMap<>();
        for (OdsSzdnGantry gantry : gantryList) {
            gantryMap.put(CommonUtil.isNull(gantry.getGantryCode()), gantry);
        }
        for (OdsLwzxsfsjFeeRecords01 feeRecords : list) {
            String vehicleplate = CommonUtil.isNull(feeRecords.getVehicleplate());
            if (vehicleplate.indexOf("_") > -1) {
                feeRecords.setVehicleplate(vehicleplate.split("_")[0]);
            }
            if (null != feeRecords.getTranstime()) {
                feeRecords.setTranstimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, feeRecords.getTranstime()));
            }
            if (null != feeRecords.getLastgantrytime()) {
                feeRecords.setLastgantrytimeStr(DateUtils.parseDateToStr(
                        DateUtils.YYYY_MM_DD_HH_MM_SS, feeRecords.getLastgantrytime()));
            }
            String gantryid = CommonUtil.isNull(feeRecords.getGantryid());
            if (gantryMap.containsKey(gantryid)) {
                OdsSzdnGantry gantry = gantryMap.get(gantryid);
                feeRecords.setGantryName(gantry.getGantryName());
                feeRecords.setSectionCodeStr(gantry.getSectionCode());
            }
        }
    }

    @GetMapping("/listToExport")
    public List<OdsLwzxsfsjFeeRecords01> listToExport(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01) {
        startPage();

        String queryQx = "noall";
        String dataQuery = CommonUtil.isNull(redisCache.getCacheObject("sys_config:data_query"));
        if (CommonUtil.isNotBlank(dataQuery)) {
            queryQx = dataQuery;
        }

        if (!queryQx.equals("queryall")) {
            String vehicleplateQuery = odsLwzxsfsjFeeRecords01.getVehicleplate();
            if (CommonUtil.isBlank(vehicleplateQuery)) {
                odsLwzxsfsjFeeRecords01.setFlag("JiAnDong");
            }
        }

        String sectionCodeStr = odsLwzxsfsjFeeRecords01.getSectionCodeStr();
        if (CommonUtil.isNotBlank(sectionCodeStr)) {
            odsLwzxsfsjFeeRecords01.setSectionList(
                    Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList()));
        }

        String code = CommonUtil.deleteEnd(odsLwzxsfsjFeeRecords01.getCode());
        if (CommonUtil.isNotBlank(code)) {
            odsLwzxsfsjFeeRecords01.setCodeList(
                    Arrays.stream(code.split(",")).collect(Collectors.toList()));
            odsLwzxsfsjFeeRecords01.setCode("");
        }

        List<OdsLwzxsfsjFeeRecords01> list =
                odsLwzxsfsjFeeRecords01Service
                        .selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01);
        decorateLegacy(list);
        return list;
    }

    /**
     * 获取基础-收费流水详细信息
     */
    @GetMapping(value = "/{bigId}")
    public OdsLwzxsfsjFeeRecords01 getInfo(@PathVariable("bigId") String bigId) {
        return odsLwzxsfsjFeeRecords01Service.selectOdsLwzxsfsjFeeRecords01ById(bigId);
    }
}
