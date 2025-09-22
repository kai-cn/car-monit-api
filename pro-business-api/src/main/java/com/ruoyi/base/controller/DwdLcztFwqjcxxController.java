package com.ruoyi.base.controller;

import com.ruoyi.base.domain.DwdLcztFwqjcxx;

import com.ruoyi.base.service.IDwdLcztFwqjcxxService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 服务区基础信息Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/fwqjcxx")
public class DwdLcztFwqjcxxController extends BaseController {

    @Autowired
    private IDwdLcztFwqjcxxService dwdLcztFwqjcxxService;

    /**
     * 查询服务区基础信息列表
     */
    @GetMapping("/list")
    public TableDataInfo list(DwdLcztFwqjcxx dwdLcztFwqjcxx) {
        startPage();
        List<DwdLcztFwqjcxx> list = dwdLcztFwqjcxxService.selectDwdLcztFwqjcxxList(dwdLcztFwqjcxx);
        return getDataTable(list);
    }
    /**
     * 获取服务区基础信息详细信息
     */
    @GetMapping(value = "/{agentPk}")
    public AjaxResult getInfo(@PathVariable("agentPk") String agentPk) {
        return AjaxResult.success(dwdLcztFwqjcxxService.selectDwdLcztFwqjcxxById(agentPk));
    }

    /*
    * 获取服务区基础信息列表
     */
    @GetMapping(value = "/listAll")
    public List<DwdLcztFwqjcxx> getListAll() {
        return dwdLcztFwqjcxxService.list();
    }
}
