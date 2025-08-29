package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsSzdnSection;
import com.ruoyi.base.mapper.OdsSzdnSectionMapper;
import com.ruoyi.base.service.IOdsSzdnSectionService;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 路段信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsSzdnSectionServiceImpl extends ServiceImpl<OdsSzdnSectionMapper, OdsSzdnSection> implements IOdsSzdnSectionService {

    @Autowired
    private OdsSzdnSectionMapper odsSzdnSectionMapper;

    /**
     * 查询路段信息
     *
     * @param id 路段信息ID
     * @return 路段信息
     */
    @Override
    public OdsSzdnSection selectOdsSzdnSectionById(String id) {
        return odsSzdnSectionMapper.selectOdsSzdnSectionById(id);
    }

    /**
     * 查询路段信息列表
     *
     * @param odsSzdnSection 路段信息
     * @return 路段信息
     */
    @Override
    public List<OdsSzdnSection> selectOdsSzdnSectionList(OdsSzdnSection odsSzdnSection) {
        return odsSzdnSectionMapper.selectOdsSzdnSectionList(odsSzdnSection);
    }
}
