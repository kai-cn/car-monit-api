package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.spring.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsYhglVBaseOrg;
import com.ruoyi.base.mapper.OdsYhglVBaseOrgMapper;
import com.ruoyi.base.service.IOdsYhglVBaseOrgService;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 机构信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsYhglVBaseOrgServiceImpl extends ServiceImpl<OdsYhglVBaseOrgMapper, OdsYhglVBaseOrg> implements IOdsYhglVBaseOrgService {

    @Autowired
    private OdsYhglVBaseOrgMapper odsYhglVBaseOrgMapper;

    /**
     * 查询机构信息
     *
     * @param bigId 机构信息ID
     * @return 机构信息
     */
    @Override
    public OdsYhglVBaseOrg selectOdsYhglVBaseOrgById(String bigId) {
        return odsYhglVBaseOrgMapper.selectOdsYhglVBaseOrgById(bigId);
    }

    /**
     * 查询机构信息列表
     *
     * @param odsYhglVBaseOrg 机构信息
     * @return 机构信息
     */
    @Override
    public List<OdsYhglVBaseOrg> selectOdsYhglVBaseOrgList(OdsYhglVBaseOrg odsYhglVBaseOrg) {
        return odsYhglVBaseOrgMapper.selectOdsYhglVBaseOrgList(odsYhglVBaseOrg);
    }
}
