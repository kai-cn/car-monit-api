package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.DwdLcztSfsjcxx;
import com.ruoyi.base.mapper.DwdLcztSfsjcxxMapper;
import com.ruoyi.base.service.IDwdLcztSfsjcxxService;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 收费所基础信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class DwdLcztSfsjcxxServiceImpl extends ServiceImpl<DwdLcztSfsjcxxMapper, DwdLcztSfsjcxx> implements IDwdLcztSfsjcxxService {

    @Autowired
    private DwdLcztSfsjcxxMapper dwdLcztSfsjcxxMapper;

    /**
     * 查询收费所基础信息
     *
     * @param agentPk 收费所基础信息ID
     * @return 收费所基础信息
     */
    @Override
    public DwdLcztSfsjcxx selectDwdLcztSfsjcxxById(String agentPk) {
        return dwdLcztSfsjcxxMapper.selectDwdLcztSfsjcxxById(agentPk);
    }

    /**
     * 查询收费所基础信息列表
     *
     * @param dwdLcztSfsjcxx 收费所基础信息
     * @return 收费所基础信息
     */
    @Override
    public List<DwdLcztSfsjcxx> selectDwdLcztSfsjcxxList(DwdLcztSfsjcxx dwdLcztSfsjcxx) {
        return dwdLcztSfsjcxxMapper.selectDwdLcztSfsjcxxList(dwdLcztSfsjcxx);
    }
}
