package com.ruoyi.base.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.base.domain.OdsSzdnGantry;
import com.ruoyi.base.mapper.OdsSzdnGantryMapper;
import com.ruoyi.base.service.IOdsSzdnGantryService;
import com.ruoyi.common.core.domain.AjaxResult;
import com.ruoyi.common.utils.CommonUtil;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

/**
 * 门架信息Service业务层处理
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Service
public class OdsSzdnGantryServiceImpl extends ServiceImpl<OdsSzdnGantryMapper, OdsSzdnGantry> implements IOdsSzdnGantryService {

    @Autowired
    private OdsSzdnGantryMapper odsSzdnGantryMapper;

    /**
     * 查询门架信息
     *
     * @param id 门架信息ID
     * @return 门架信息
     */
    @Override
    public OdsSzdnGantry selectOdsSzdnGantryById(String id) {
        return odsSzdnGantryMapper.selectOdsSzdnGantryById(id);
    }

    /**
     * 查询门架信息列表
     *
     * @param odsSzdnGantry 门架信息
     * @return 门架信息
     */
    @Override
    public List<OdsSzdnGantry> selectOdsSzdnGantryList(OdsSzdnGantry odsSzdnGantry) {
        return odsSzdnGantryMapper.selectOdsSzdnGantryList(odsSzdnGantry);
    }
}
