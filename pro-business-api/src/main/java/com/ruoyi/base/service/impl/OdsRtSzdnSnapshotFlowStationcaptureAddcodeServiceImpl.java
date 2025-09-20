package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.mapper.OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper;
import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService;
import com.ruoyi.common.utils.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.*;
import java.util.stream.Collectors;

/**
 * 收费站抓拍Service业务层处理
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Service
public class OdsRtSzdnSnapshotFlowStationcaptureAddcodeServiceImpl extends ServiceImpl<OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper, OdsRtSzdnSnapshotFlowStationcaptureAddcode> implements IOdsRtSzdnSnapshotFlowStationcaptureAddcodeService {

    @Autowired
    private OdsRtSzdnSnapshotFlowStationcaptureAddcodeMapper odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper;

    /**
     * 查询收费站抓拍
     *
     * @param bigId 收费站抓拍ID
     * @return 收费站抓拍
     */
    @Override
    public OdsRtSzdnSnapshotFlowStationcaptureAddcode selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(Long bigId) {
        return odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeById(bigId);
    }

    /**
     * 查询收费站抓拍列表
     *
     * @param odsRtSzdnSnapshotFlowStationcaptureAddcode 收费站抓拍
     * @return 收费站抓拍
     */
    @Override
    public List<OdsRtSzdnSnapshotFlowStationcaptureAddcode> selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(OdsRtSzdnSnapshotFlowStationcaptureAddcode odsRtSzdnSnapshotFlowStationcaptureAddcode) {
        return odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeList(odsRtSzdnSnapshotFlowStationcaptureAddcode);
    }

    /**
     * 根据UUID 查询
     * @param queryUuids
     * @return
     */
    @Override
    public Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByQueryUuids(String queryUuids) {
        Map<String, OdsRtSzdnSnapshotFlowStationcaptureAddcode> map = new HashMap<>();
        if(StringUtils.isNotBlank(queryUuids)) {
            String[] split = queryUuids.split(",");
            List<String> uuidList = Arrays.stream(split).collect(Collectors.toList());
            List<OdsRtSzdnSnapshotFlowStationcaptureAddcode> list = odsRtSzdnSnapshotFlowStationcaptureAddcodeMapper.selectOdsRtSzdnSnapshotFlowStationcaptureAddcodeByUuidList(uuidList);
            for (OdsRtSzdnSnapshotFlowStationcaptureAddcode rtn :list){
                map.put(rtn.getDatauuid(),rtn);
            }
        }
        return map;
    }
}
