package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsSzdnGantry;
import com.ruoyi.base.service.IOdsSzdnGantryService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 门架信息Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/gantry")
public class OdsSzdnGantryController extends BaseController {

    @Autowired
    private IOdsSzdnGantryService odsSzdnGantryService;

    /**
     * 查询门架信息列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsSzdnGantry odsSzdnGantry) {
        startPage();
        List<OdsSzdnGantry> list = odsSzdnGantryService.selectOdsSzdnGantryList(odsSzdnGantry);
        return getDataTable(list);
    }

    /**
     * 获取门架信息详细信息
     */
    @GetMapping(value = "/{id}")
    public AjaxResult getInfo(@PathVariable("id") String id) {
        return AjaxResult.success(odsSzdnGantryService.selectOdsSzdnGantryById(id));
    }

    /**
     * 获取门架信息列表
     * @return
     */
    @GetMapping(value = "/listAll")
    public List<OdsSzdnGantry> getListAll() {
        return odsSzdnGantryService.list();
    }
}
