package com.ruoyi.base.controller;

import com.ruoyi.base.domain.BaseGantrySnapshotFlow;
import com.ruoyi.base.service.IBaseGantrySnapshotFlowService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 门架抓拍流水Controller
 *
 * @author ruoyi
 * @date 2025-08-25
 */
@RestController
@RequestMapping("/base/gantrysnapshotflow")
public class BaseGantrySnapshotFlowController extends BaseController {

    @Autowired
    private IBaseGantrySnapshotFlowService baseGantrySnapshotFlowService;

    /**
     * 查询门架抓拍流水列表
     */
    @GetMapping("/list")
    public TableDataInfo list(BaseGantrySnapshotFlow baseGantrySnapshotFlow) {
        startPage();
        // baseGantrySnapshotFlow.setTenantId(SecurityUtils.getTenantId()); // 查询我自己单位的租户
        List<BaseGantrySnapshotFlow> list = baseGantrySnapshotFlowService.selectBaseGantrySnapshotFlowList(baseGantrySnapshotFlow);
        return getDataTable(list);
    }



    /**
     * 获取门架抓拍流水详细信息
     */
    @GetMapping(value = "/{bigId}")
    public AjaxResult getInfo(@PathVariable("bigId") Long bigId) {
        return AjaxResult.success(baseGantrySnapshotFlowService.selectBaseGantrySnapshotFlowById(bigId));
    }

    /**
     * 新增门架抓拍流水
     */
    @PostMapping
    public AjaxResult add(@RequestBody BaseGantrySnapshotFlow baseGantrySnapshotFlow) {
        return baseGantrySnapshotFlowService.saveBaseGantrySnapshotFlow(baseGantrySnapshotFlow);
    }

    /**
     * 修改门架抓拍流水
     */
    @PutMapping
    public AjaxResult edit(@RequestBody BaseGantrySnapshotFlow baseGantrySnapshotFlow) {
        return baseGantrySnapshotFlowService.saveBaseGantrySnapshotFlow(baseGantrySnapshotFlow);
    }

    /**
     * 删除门架抓拍流水
     */
    @DeleteMapping("/{bigIds}")
    public AjaxResult remove(@PathVariable Long[] bigIds) {
        return baseGantrySnapshotFlowService.deleteBaseGantrySnapshotFlowByIds(bigIds);
    }

}
