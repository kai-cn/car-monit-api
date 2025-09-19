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
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService;
import com.ruoyi.common.core.page.TableDataInfo;

/**
 * 收费站抓拍Controller
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@RestController
@RequestMapping("/base/stationcapture")
public class OdsRtSzdnSnapshotFlowStationcaptureAddcodeController extends BaseController {

    @Autowired
    private IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService odsRtSzdnSnapshotFlowStationcaptureAddcodeService;

    /**
     * 查询收费站抓拍列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsRtSzdnSnapshotFlowStationcaptureAddcode odsRtSzdnSnapshotFlowStationcaptureAddcode) {
        startPage();
        // odsRtSzdnSnapshotFlowStationcaptureAddcode.setTenantId(SecurityUtils.getTenantId()); // 查询我自己单位的租户
        List<OdsRtSzdnSnapshotFlowStationcaptureAddcode> list = odsRtSzdnSnapshotFlowStationcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(odsRtSzdnSnapshotFlowStationcaptureAddcode);
        return getDataTable(list);
    }


    /**
     * 获取收费站抓拍详细信息
     */
    @GetMapping(value = "/{bigId}")
    public AjaxResult getInfo(@PathVariable("bigId") Long bigId) {
        return AjaxResult.success(odsRtSzdnSnapshotFlowStationcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(bigId));
    }

    @GetMapping("/map")
    public Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> map(OdsRtSzdnSnapshotFlowStationcaptureAddcode bo) {
        bo.setQueryUuids("91d4c03b-39ac-4c74-9c9c-0378e6ad17b5," +
                            "f4bdc92d-bfd4-4201-8769-aff688276b85," +
                            "48861e72-5ebf-4699-b068-4e7099ca05fc," +
                            "91dfe837-1285-44c6-b4c8-7a62f7a3ad30," +
                            "91dfe837-1285-44c6-b4c8-7a62f7a3ad30," +
                            "f12bf756-ad07-454d-bc9d-2107022dc798," +
                            "ba0cfd6f-6d16-44fa-82f3-93b2e3fde1b7," +
                            "e4b3a3ad-6ac2-4a32-900d-f1e81c0988c7," +
                            "567d1762-94d4-460f-8fcc-64fa234e622f," +
                            "1b06a749-1693-4733-86a2-b98a928edb53");
        return odsRtSzdnSnapshotFlowStationcaptureAddcodeService.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(bo);
    }


}
