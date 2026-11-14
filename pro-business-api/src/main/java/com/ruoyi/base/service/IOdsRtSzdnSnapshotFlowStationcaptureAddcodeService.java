package com.ruoyi.base.service;

import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode;
import java.util.List;
import java.util.Map;

import com.baomidou.mybatisplus.spring.service.IService;

/**
 * 收费站抓拍Service接口
 *
 * @author ruoyi
 * @date 2025-09-18
 */
public interface IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService extends IService<OdsRtSzdnSnapshotFlowStationcaptureAddcode> {
    /**
     * 查询收费站抓拍
     *
     * @param bigId 收费站抓拍ID
     * @return 收费站抓拍
     */
    OdsRtSzdnSnapshotFlowStationcaptureAddcode selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(Long bigId);

    /**
     * 查询收费站抓拍列表
     *
     * @param odsRtSzdnSnapshotFlowStationcaptureAddcode 收费站抓拍
     * @return 收费站抓拍集合
     */
    List<OdsRtSzdnSnapshotFlowStationcaptureAddcode> selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(OdsRtSzdnSnapshotFlowStationcaptureAddcode odsRtSzdnSnapshotFlowStationcaptureAddcode);

    /**
     * 根据UUID 查询
     * @param queryUuids
     * @return
     */
    Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(String queryUuids,String applyTime1,String applyTime2);
}
