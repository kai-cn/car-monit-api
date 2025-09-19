package com.ruoyi.base.controller;

import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure;
import com.ruoyi.base.service.IOdsSzdnProvinceBorderVehicleWeightNewstructureService;
import com.ruoyi.common.core.page.TableDataInfo;

/**
 * 省界称重Controller
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@RestController
@RequestMapping("/base/vehicleweight")
public class OdsSzdnProvinceBorderVehicleWeightNewstructureController extends BaseController {

    @Autowired
    private IOdsSzdnProvinceBorderVehicleWeightNewstructureService odsSzdnProvinceBorderVehicleWeightNewstructureService;

    /**
     * 查询省界称重列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsSzdnProvinceBorderVehicleWeightNewstructure odsSzdnProvinceBorderVehicleWeightNewstructure) {
        startPage();
        // odsSzdnProvinceBorderVehicleWeightNewstructure.setTenantId(SecurityUtils.getTenantId()); // 查询我自己单位的租户
        List<OdsSzdnProvinceBorderVehicleWeightNewstructure> list = odsSzdnProvinceBorderVehicleWeightNewstructureService.selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(odsSzdnProvinceBorderVehicleWeightNewstructure);
        return getDataTable(list);
    }


    /**
     * 获取省界称重详细信息
     */
    @GetMapping(value = "/{dataSource}")
    public AjaxResult getInfo(@PathVariable("dataSource") String dataSource) {
        return AjaxResult.success(odsSzdnProvinceBorderVehicleWeightNewstructureService.selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(dataSource));
    }

    @GetMapping("/map")
    public Map<String, OdsSzdnProvinceBorderVehicleWeightNewstructure> map(OdsSzdnProvinceBorderVehicleWeightNewstructure bo) {
        bo.setQueryUuids("18f8e2af-6ebe-4b33-8f37-a688f441de37,7379e7aa-e325-449b-9728-b8f6940c77f1,67fb6580-6b8a-4649-abd7-632dc71c4799");
        return odsSzdnProvinceBorderVehicleWeightNewstructureService.selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(bo);
    }





}
