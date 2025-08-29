package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsSzdnSection;
import com.ruoyi.base.service.IOdsSzdnSectionService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 路段信息Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/section")
public class OdsSzdnSectionController extends BaseController {

    @Autowired
    private IOdsSzdnSectionService odsSzdnSectionService;

    /**
     * 查询路段信息列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsSzdnSection odsSzdnSection) {
        startPage();
        List<OdsSzdnSection> list = odsSzdnSectionService.selectOdsSzdnSectionList(odsSzdnSection);
        return getDataTable(list);
    }

    /**
     * 获取路段信息详细信息
     */
    @GetMapping(value = "/{id}")
    public AjaxResult getInfo(@PathVariable("id") String id) {
        return AjaxResult.success(odsSzdnSectionService.selectOdsSzdnSectionById(id));
    }

    /**
     * 查询所有路段信息列表
     * @return
     */
    @GetMapping(value = "/listAll")
    public AjaxResult getListAll() {
        return AjaxResult.success(odsSzdnSectionService.list());
    }
}
