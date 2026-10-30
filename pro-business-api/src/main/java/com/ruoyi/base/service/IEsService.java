package com.ruoyi.base.service;

import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;

public interface IEsService {
    boolean saveSnapshotFlow(OdsRtSzdnSnapshotFlowAddcode flowData);
    boolean deleteSnapshotFlow(String dataId);
}
