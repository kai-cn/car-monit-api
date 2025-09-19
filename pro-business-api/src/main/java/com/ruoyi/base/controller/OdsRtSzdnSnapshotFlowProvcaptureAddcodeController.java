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
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService;
import com.ruoyi.common.core.page.TableDataInfo;

/**
 * 省界抓拍Controller
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@RestController
@RequestMapping("/base/provcapture")
public class OdsRtSzdnSnapshotFlowProvcaptureAddcodeController extends BaseController {

    @Autowired
    private IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService odsRtSzdnSnapshotFlowProvcaptureAddcodeService;

    /**
     * 查询省界抓拍列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsRtSzdnSnapshotFlowProvcaptureAddcode odsRtSzdnSnapshotFlowProvcaptureAddcode) {
        startPage();
        // odsRtSzdnSnapshotFlowProvcaptureAddcode.setTenantId(SecurityUtils.getTenantId()); // 查询我自己单位的租户
        List<OdsRtSzdnSnapshotFlowProvcaptureAddcode> list = odsRtSzdnSnapshotFlowProvcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(odsRtSzdnSnapshotFlowProvcaptureAddcode);
        return getDataTable(list);
    }


    /**
     * 获取省界抓拍详细信息
     */
    @GetMapping(value = "/{bigId}")
    public AjaxResult getInfo(@PathVariable("bigId") Long bigId) {
        return AjaxResult.success(odsRtSzdnSnapshotFlowProvcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(bigId));
    }

    @GetMapping("/map")
    public Map<String, OdsRtSzdnSnapshotFlowProvcaptureAddcode> map(OdsRtSzdnSnapshotFlowProvcaptureAddcode bo) {
        bo.setQueryUuids("e4b3a3ad-6ac2-4a32-900d-f1e81c0988c7,ba0cfd6f-6d16-44fa-82f3-93b2e3fde1b7,91dfe837-1285-44c6-b4c8-7a62f7a3ad3048861e72-5ebf-4699-b068-4e7099ca05fc");
        return odsRtSzdnSnapshotFlowProvcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(bo);
    }


}
