package com.ruoyi.base.controller;

import com.ruoyi.base.domain.DwdLcztSfsjcxx;
import com.ruoyi.base.service.IDwdLcztSfsjcxxService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 收费所基础信息Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/sfsjcxx")
public class DwdLcztSfsjcxxController extends BaseController {

    @Autowired
    private IDwdLcztSfsjcxxService dwdLcztSfsjcxxService;

    /**
     * 查询收费所基础信息列表
     */
    @GetMapping("/list")
    public TableDataInfo list(DwdLcztSfsjcxx dwdLcztSfsjcxx) {
        startPage();
        List<DwdLcztSfsjcxx> list = dwdLcztSfsjcxxService.selectDwdLcztSfsjcxxList(dwdLcztSfsjcxx);
        return getDataTable(list);
    }

    /**
     * 获取收费所基础信息详细信息
     */
    @GetMapping(value = "/{agentPk}")
    public AjaxResult getInfo(@PathVariable("agentPk") String agentPk) {
        return AjaxResult.success(dwdLcztSfsjcxxService.selectDwdLcztSfsjcxxById(agentPk));
    }

    /**
     * 获取收费所基础信息列表
     * @return
     */
    @GetMapping(value = "/listAll")
    public AjaxResult getListAll() {
        return AjaxResult.success(dwdLcztSfsjcxxService.list());
    }
}
