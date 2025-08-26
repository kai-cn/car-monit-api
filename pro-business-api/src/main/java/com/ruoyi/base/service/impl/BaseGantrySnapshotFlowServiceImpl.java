package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import com.ruoyi.base.mapper.BaseGantrySnapshotFlowMapper;
import com.ruoyi.base.domain.BaseGantrySnapshotFlow;
import com.ruoyi.base.service.IBaseGantrySnapshotFlowService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 门架抓拍流水Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-25
 */
@Service
public class BaseGantrySnapshotFlowServiceImpl extends ServiceImpl<BaseGantrySnapshotFlowMapper, BaseGantrySnapshotFlow> implements IBaseGantrySnapshotFlowService {

    @Autowired
    private BaseGantrySnapshotFlowMapper baseGantrySnapshotFlowMapper;

    /**
     * 查询门架抓拍流水
     *
     * @param bigId 门架抓拍流水ID
     * @return 门架抓拍流水
     */
    @Override
    public BaseGantrySnapshotFlow selectBaseGantrySnapshotFlowById(String bigId) {
        return baseGantrySnapshotFlowMapper.selectBaseGantrySnapshotFlowById(bigId);
    }

    /**
     * 查询门架抓拍流水列表
     *
     * @param baseGantrySnapshotFlow 门架抓拍流水
     * @return 门架抓拍流水
     */
    @Override
    public List<BaseGantrySnapshotFlow> selectBaseGantrySnapshotFlowList(BaseGantrySnapshotFlow baseGantrySnapshotFlow) {
        return baseGantrySnapshotFlowMapper.selectBaseGantrySnapshotFlowList(baseGantrySnapshotFlow);
    }





}
