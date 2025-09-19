package com.ruoyi.base.controller;

import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
import com.ruoyi.common.core.controller.BaseController;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.core.page.TableDataInfo;
import com.ruoyi.common.utils.DateUtils;
import com.ruoyi.common.utils.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 门架抓拍流水Controller
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@RestController
@RequestMapping("/base/snapshotflow")
public class OdsRtSzdnSnapshotFlowAddcodeController extends BaseController {

    @Autowired
    private IOdsRtSzdnSnapshotFlowAddcodeService odsRtSzdnSnapshotFlowAddcodeService;

    /**
     * 查询门架抓拍流水列表
     */
    @GetMapping("/list")
    public TableDataInfo list(OdsRtSzdnSnapshotFlowAddcode odsRtSzdnSnapshotFlowAddcode) {
        startPage();
        List<OdsRtSzdnSnapshotFlowAddcode> list = odsRtSzdnSnapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode);
        if (null !=list && list.size() > 0){
            for (OdsRtSzdnSnapshotFlowAddcode rtn :list){
                rtn.setId(StringUtils.getUUID());
                // 抓拍时间格式化
                if (null != rtn.getSnapshottime()) {
                    rtn.setSnapshottimeStr( DateUtils.parseDateToStr(DateUtils.YYYY_MM_DD_HH_MM_SS, rtn.getSnapshottime()));
                }
            }
        }
        return getDataTable(list);
    }

    /**
     * 获取门架抓拍流水详细信息
     */
    @GetMapping(value = "/{bigId}")
    public AjaxResult getInfo(@PathVariable("bigId") String bigId) {
        return AjaxResult.success(odsRtSzdnSnapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeById(bigId));
    }




    @GetMapping("/map")
    public Map<String, OdsRtSzdnSnapshotFlowAddcode> map(OdsRtSzdnSnapshotFlowAddcode bo) {
        bo.setQueryUuids("18f8e2af-6ebe-4b33-8f37-a688f441de37,7379e7aa-e325-449b-9728-b8f6940c77f1,67fb6580-6b8a-4649-abd7-632dc71c4799");
        return odsRtSzdnSnapshotFlowAddcodeService.selectOdsRtSzdnSnapshotFlowAddcodeByQueryUuids(bo);
    }
}
