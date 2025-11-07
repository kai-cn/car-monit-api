package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01;
import com.ruoyi.base.domain.OdsSzdnGantry;
import com.ruoyi.base.service.IOdsLwzxsfsjFeeRecords01Service;
import com.ruoyi.base.service.IOdsSzdnGantryService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 基础-收费流水Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/feerecords")
public class OdsLwzxsfsjFeeRecords01Controller extends BaseController {

    @Autowired
    private IOdsLwzxsfsjFeeRecords01Service odsLwzxsfsjFeeRecords01Service;

    @Autowired
    private IOdsSzdnGantryService odsSzdnGantryService;

    /**
     * 查询基础-收费流水列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01) {
        startPage();

        // 权限只能查询吉安东
        String vehicleplateQuery = odsLwzxsfsjFeeRecords01.getVehicleplate();
        if (CommonUtil.isBlank(vehicleplateQuery)) {
            odsLwzxsfsjFeeRecords01.setFlag("JiAnDong");
        }
        // 路段
        String sectionCodeStr = odsLwzxsfsjFeeRecords01.getSectionCodeStr();
        if (CommonUtil.isNotBlank(sectionCodeStr)){
            odsLwzxsfsjFeeRecords01.setSectionList(Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList()));
        }

        // 门架
        String code = CommonUtil.deleteEnd(odsLwzxsfsjFeeRecords01.getCode());
        if (CommonUtil.isNotBlank(code)){
            // 服务区 收费站
            odsLwzxsfsjFeeRecords01.setCodeList(Arrays.stream(code.split(",")).collect(Collectors.toList()));
            odsLwzxsfsjFeeRecords01.setCode(""); // 查询范围
        }
        List<OdsLwzxsfsjFeeRecords01> list = odsLwzxsfsjFeeRecords01Service.selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01);

        if (null !=list && list.size() > 0){

            List<OdsSzdnGantry>  gantryList = odsSzdnGantryService.getGantryRedis();
            Map<String,String> gantryMao = new HashMap<>();
            for (OdsSzdnGantry rtnOdsSzdnGantry:gantryList){
                gantryMao.put(CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode()),rtnOdsSzdnGantry.getGantryName());
            }


            for (OdsLwzxsfsjFeeRecords01 feeRecords:list){
                String vehicleplate = CommonUtil.isNull(feeRecords.getVehicleplate());
                if (vehicleplate.indexOf("_") > -1){
                    String[] vehicleplateStr = vehicleplate.split("_");
                    feeRecords.setVehicleplate(vehicleplateStr[0]);
                    /*if (vehicleplateStr.length >1){
                        feeRecords.setPlateColor(vehicleplateStr[1]);
                    }*/
                    String gantryid = CommonUtil.isNull(feeRecords.getGantryid());
                    if (gantryMao.containsKey(gantryid)){
                        feeRecords.setGantryName(gantryMao.get(gantryid));
                    }
                }
            }
        }

        return getDataTable(list);
    }


    @GetMapping("/listToExport")
    public List<OdsLwzxsfsjFeeRecords01> listToExport(OdsLwzxsfsjFeeRecords01 odsLwzxsfsjFeeRecords01) {
        startPage();

        // 权限只能查询吉安东
        String vehicleplateQuery = odsLwzxsfsjFeeRecords01.getVehicleplate();
        if (CommonUtil.isBlank(vehicleplateQuery)) {
            odsLwzxsfsjFeeRecords01.setFlag("JiAnDong");
        }

        // 路段
        String sectionCodeStr = odsLwzxsfsjFeeRecords01.getSectionCodeStr();
        if (CommonUtil.isNotBlank(sectionCodeStr)) {
            odsLwzxsfsjFeeRecords01.setSectionList(Arrays.stream(sectionCodeStr.split(",")).collect(Collectors.toList()));
        }

        // 门架
        String code = CommonUtil.deleteEnd(odsLwzxsfsjFeeRecords01.getCode());
        if (CommonUtil.isNotBlank(code)) {
            // 服务区 收费站
            odsLwzxsfsjFeeRecords01.setCodeList(Arrays.stream(code.split(",")).collect(Collectors.toList()));
            odsLwzxsfsjFeeRecords01.setCode(""); // 查询范围
        }

        List<OdsLwzxsfsjFeeRecords01> list = odsLwzxsfsjFeeRecords01Service.selectOdsLwzxsfsjFeeRecords01List(odsLwzxsfsjFeeRecords01);

        if (null !=list && list.size() > 0){

            List<OdsSzdnGantry>  gantryList = odsSzdnGantryService.getGantryRedis();
            Map<String,String> gantryMao = new HashMap<>();
            for (OdsSzdnGantry rtnOdsSzdnGantry:gantryList){
                gantryMao.put(CommonUtil.isNull(rtnOdsSzdnGantry.getGantryCode()),rtnOdsSzdnGantry.getGantryName());
            }


            for (OdsLwzxsfsjFeeRecords01 feeRecords:list){
                String vehicleplate = CommonUtil.isNull(feeRecords.getVehicleplate());
                if (vehicleplate.indexOf("_") > -1){
                    String[] vehicleplateStr = vehicleplate.split("_");
                    feeRecords.setVehicleplate(vehicleplateStr[0]);
                    /*if (vehicleplateStr.length >1){
                        feeRecords.setPlateColor(vehicleplateStr[1]);
                    }*/
                    String gantryid = CommonUtil.isNull(feeRecords.getGantryid());
                    if (gantryMao.containsKey(gantryid)){
                        feeRecords.setGantryName(gantryMao.get(gantryid));
                    }
                }
            }
        }
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
