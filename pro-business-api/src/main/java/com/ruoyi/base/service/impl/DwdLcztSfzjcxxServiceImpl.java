package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.DwdLcztSfzjcxx;
import com.ruoyi.base.mapper.DwdLcztSfzjcxxMapper;
import com.ruoyi.base.service.IDwdLcztSfzjcxxService;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 收费站基础信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class DwdLcztSfzjcxxServiceImpl extends ServiceImpl<DwdLcztSfzjcxxMapper, DwdLcztSfzjcxx> implements IDwdLcztSfzjcxxService {

    @Autowired
    private DwdLcztSfzjcxxMapper dwdLcztSfzjcxxMapper;

    /**
     * 查询收费站基础信息
     *
     * @param agentPk 收费站基础信息ID
     * @return 收费站基础信息
     */
    @Override
    public DwdLcztSfzjcxx selectDwdLcztSfzjcxxById(String agentPk) {
        return dwdLcztSfzjcxxMapper.selectDwdLcztSfzjcxxById(agentPk);
    }

    /**
     * 查询收费站基础信息列表
     *
     * @param dwdLcztSfzjcxx 收费站基础信息
     * @return 收费站基础信息
     */
    @Override
    public List<DwdLcztSfzjcxx> selectDwdLcztSfzjcxxList(DwdLcztSfzjcxx dwdLcztSfzjcxx) {
        return dwdLcztSfzjcxxMapper.selectDwdLcztSfzjcxxList(dwdLcztSfzjcxx);
    }
}
