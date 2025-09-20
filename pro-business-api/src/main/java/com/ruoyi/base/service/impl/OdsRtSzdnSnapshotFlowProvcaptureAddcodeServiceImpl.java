package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService;
import com.ruoyi.common.utils.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 省界抓拍Service业务层处理
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Service
public class OdsRtSzdnSnapshotFlowProvcaptureAddcodeServiceImpl extends ServiceImpl<OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper, OdsRtSzdnSnapshotFlowProvcaptureAddcode> implements IOdsRtSzdnSnapshotFlowProvcaptureAddcodeService {

    @Autowired
    private OdsRtSzdnSnapshotFlowProvcaptureAddcodeMapper odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper;

    /**
     * 查询省界抓拍
     *
     * @param bigId 省界抓拍ID
     * @return 省界抓拍
     */
    @Override
    public OdsRtSzdnSnapshotFlowProvcaptureAddcode selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(Long bigId) {
        return odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeById(bigId);
    }

    /**
     * 查询省界抓拍列表
     *
     * @param odsRtSzdnSnapshotFlowProvcaptureAddcode 省界抓拍
     * @return 省界抓拍
     */
    @Override
    public List<OdsRtSzdnSnapshotFlowProvcaptureAddcode> selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(OdsRtSzdnSnapshotFlowProvcaptureAddcode odsRtSzdnSnapshotFlowProvcaptureAddcode) {
        return odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeList(odsRtSzdnSnapshotFlowProvcaptureAddcode);
    }


    /**
     * 根据UUID 查询
     * @param queryUuids
     * @return
     */
    @Override
    public Map<String, OdsRtSzdnSnapshotFlowProvcaptureAddcode> selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByQueryUuids(String queryUuids) {
        Map<String, OdsRtSzdnSnapshotFlowProvcaptureAddcode> map = new HashMap<>();
        if (StringUtils.isNotBlank(queryUuids)) {
            List<String> uuidList = Arrays.stream(queryUuids.split(",")).collect(Collectors.toList());
            List<OdsRtSzdnSnapshotFlowProvcaptureAddcode> list = odsRtSzdnSnapshotFlowProvcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowProvcaptureAddcodeByUuidList(uuidList);
            for (OdsRtSzdnSnapshotFlowProvcaptureAddcode rtn : list) {
                map.put(rtn.getDatauuid(),rtn);
            }
        }
        return map;
    }
}
