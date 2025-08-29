package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsYhglVBaseOrg;
import com.ruoyi.base.service.IOdsYhglVBaseOrgService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 机构信息Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/org")
public class OdsYhglVBaseOrgController extends BaseController {

    @Autowired
    private IOdsYhglVBaseOrgService odsYhglVBaseOrgService;

    /**
     * 查询机构信息列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsYhglVBaseOrg odsYhglVBaseOrg) {
        startPage();
        List<OdsYhglVBaseOrg> list = odsYhglVBaseOrgService.selectOdsYhglVBaseOrgList(odsYhglVBaseOrg);
        return getDataTable(list);
    }

    /**
     * 获取机构信息详细信息
     */
    @GetMapping(value = "/{bigId}")
    public AjaxResult getInfo(@PathVariable("bigId") String bigId) {
        return AjaxResult.success(odsYhglVBaseOrgService.selectOdsYhglVBaseOrgById(bigId));
    }

    /**
     * 获取机构信息列表
     * @return
     */
    @GetMapping(value = "/listAll")
    public AjaxResult getListAll() {
        return AjaxResult.success(odsYhglVBaseOrgService.list());
    }
}
