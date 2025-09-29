package com.ruoyi.base.controller;

import com.ruoyi.base.domain.DwdLcztSfzjcxx;
import com.ruoyi.base.service.IDwdLcztSfzjcxxService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 收费站基础信息Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/sfzjcxx")
public class DwdLcztSfzjcxxController extends BaseController {

    @Autowired
    private IDwdLcztSfzjcxxService dwdLcztSfzjcxxService;

    /**
     * 查询收费站基础信息列表
     */
    @GetMapping("/list")
    public TableDataInfo list(DwdLcztSfzjcxx dwdLcztSfzjcxx) {
        startPage();
        List<DwdLcztSfzjcxx> list = dwdLcztSfzjcxxService.selectDwdLcztSfzjcxxList(dwdLcztSfzjcxx);
        return getDataTable(list);
    }

    /**
     * 获取收费站基础信息详细信息
     */
    @GetMapping(value = "/{agentPk}")
    public AjaxResult getInfo(@PathVariable("agentPk") String agentPk) {
        return AjaxResult.success(dwdLcztSfzjcxxService.selectDwdLcztSfzjcxxById(agentPk));
    }

    /**
     * 获取收费站基础信息列表
     * @return
     */
    @GetMapping(value = "/listAll")
    public List<DwdLcztSfzjcxx> getListAll() {
        return dwdLcztSfzjcxxService.selectDwdLcztSfzjcxxList(new DwdLcztSfzjcxx());
    }
}
