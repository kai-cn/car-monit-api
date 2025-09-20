package com.ruoyi.base.service;

import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode;
import java.util.List;
import java.util.Map;

import com.baomidou.mybatisplus.extension.service.IService;

/**
 * 省界抓拍Service接口
 *
 * @author ruoyi
 * @date 2025-09-18
 */
public interface IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService extends IService<OdsRtSzdnSnapshotFlowProvcaptureAddcode> {
    /**
     * 查询省界抓拍
     *
     * @param bigId 省界抓拍ID
     * @return 省界抓拍
     */
    OdsRtSzdnSnapshotFlowProvcaptureAddcode selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(Long bigId);

    /**
     * 查询省界抓拍列表
     *
     * @param odsRtSzdnSnapshotFlowProvcaptureAddcode 省界抓拍
     * @return 省界抓拍集合
     */
    List<OdsRtSzdnSnapshotFlowProvcaptureAddcode> selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(OdsRtSzdnSnapshotFlowProvcaptureAddcode odsRtSzdnSnapshotFlowProvcaptureAddcode);

    /**
     * 根据UUID 查询
     * @param queryUuids
     * @return
     */
    Map<String, OdsRtSzdnSnapshotFlowProvcaptureAddcode> selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(String queryUuids);



}
