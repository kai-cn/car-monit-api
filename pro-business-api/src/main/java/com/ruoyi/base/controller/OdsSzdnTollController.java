package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsSzdnToll;
import com.ruoyi.base.service.IOdsSzdnTollService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

/**
 * 收费站基础信息Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/toll")
public class OdsSzdnTollController extends BaseController {

    @Autowired
    private IOdsSzdnTollService odsSzdnTollService;

    /**
     * 查询收费站基础信息列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsSzdnToll odsSzdnToll) {
        startPage();
        List<OdsSzdnToll> list = odsSzdnTollService.selectOdsSzdnTollList(odsSzdnToll);
        return getDataTable(list);
    }

    /**
     * 获取收费站基础信息详细信息
     */
    @GetMapping(value = "/{id}")
    public AjaxResult getInfo(@PathVariable("id") String id) {
        return AjaxResult.success(odsSzdnTollService.selectOdsSzdnTollById(id));
    }

    /**
     * 获取收费站基础信息列表
     */
    @GetMapping(value = "/listAll")
    public List<OdsSzdnToll> getListAll() {
        return odsSzdnTollService.list();
    }
}
