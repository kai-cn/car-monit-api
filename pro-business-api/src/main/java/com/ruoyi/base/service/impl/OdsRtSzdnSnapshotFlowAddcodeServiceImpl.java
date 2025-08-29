package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowAddcodeMapper;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 门架抓拍流水Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsRtSzdnSnapshotFlowAddcodeServiceImpl extends ServiceImpl<OdsRtSzdnSnapshotFlowAddcodeMapper, OdsRtSzdnSnapshotFlowAddcode> implements IOdsRtSzdnSnapshotFlowAddcodeService {

    @Autowired
    private OdsRtSzdnSnapshotFlowAddcodeMapper odsRtSzdnSnapshotFlowAddcodeMapper;

    /**
     * 查询门架抓拍流水
     *
     * @param bigId 门架抓拍流水ID
     * @return 门架抓拍流水
     */
    @Override
    public OdsRtSzdnSnapshotFlowAddcode selectOdsRtSzdnSnapshotFlowAddcodeById(String bigId) {
        return odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeById(bigId);
    }

    /**
     * 查询门架抓拍流水列表
     *
     * @param odsRtSzdnSnapshotFlowAddcode 门架抓拍流水
     * @return 门架抓拍流水
     */
    @Override
    public List<OdsRtSzdnSnapshotFlowAddcode> selectOdsRtSzdnSnapshotFlowAddcodeList(OdsRtSzdnSnapshotFlowAddcode odsRtSzdnSnapshotFlowAddcode) {
        return odsRtSzdnSnapshotFlowAddcodeMapper.selectOdsRtSzdnSnapshotFlowAddcodeList(odsRtSzdnSnapshotFlowAddcode);
    }
}
