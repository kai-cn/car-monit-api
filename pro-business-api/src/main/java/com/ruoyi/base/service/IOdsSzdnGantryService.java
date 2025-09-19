package com.ruoyi.base.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.base.domain.OdsSzdnGantry;

import java.util.List;
import java.util.Map;

/**
 * 门架信息Service接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
public interface IOdsSzdnGantryService extends IService<OdsSzdnGantry> {
    /**
     * 查询门架信息
     *
     * @param id 门架信息ID
     * @return 门架信息
     */
    OdsSzdnGantry selectOdsSzdnGantryById(String id);

    /**
     * 查询门架信息列表
     *
     * @param odsSzdnGantry 门架信息
     * @return 门架信息集合
     */
    List<OdsSzdnGantry> selectOdsSzdnGantryList(OdsSzdnGantry odsSzdnGantry);

    /**
     * 查询门架信息列表
     *
     * @param odsSzdnGantry 门架信息
     * @return 门架信息集合
     */
    Map<String,OdsSzdnGantry> selectOdsSzdnGantryMap(OdsSzdnGantry odsSzdnGantry);
}
