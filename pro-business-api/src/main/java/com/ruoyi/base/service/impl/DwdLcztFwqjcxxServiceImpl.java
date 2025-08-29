package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.DwdLcztFwqjcxx;
import com.ruoyi.base.mapper.DwdLcztFwqjcxxMapper;
import com.ruoyi.base.service.IDwdLcztFwqjcxxService;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 服务区基础信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class DwdLcztFwqjcxxServiceImpl extends ServiceImpl<DwdLcztFwqjcxxMapper, DwdLcztFwqjcxx> implements IDwdLcztFwqjcxxService {

    @Autowired
    private DwdLcztFwqjcxxMapper dwdLcztFwqjcxxMapper;

    /**
     * 查询服务区基础信息
     *
     * @param agentPk 服务区基础信息ID
     * @return 服务区基础信息
     */
    @Override
    public DwdLcztFwqjcxx selectDwdLcztFwqjcxxById(String agentPk) {
        return dwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxById(agentPk);
    }

    /**
     * 查询服务区基础信息列表
     *
     * @param dwdLcztFwqjcxx 服务区基础信息
     * @return 服务区基础信息
     */
    @Override
    public List<DwdLcztFwqjcxx> selectDwdLcztFwqjcxxList(DwdLcztFwqjcxx dwdLcztFwqjcxx) {
        return dwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxList(dwdLcztFwqjcxx);
    }
}
