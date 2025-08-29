package com.ruoyi.base.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.base.domain.OdsSzdnSection;
import com.ruoyi.common.core.domain.AjaxResult;

import java.util.List;

/**
 * 路段信息Service接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
public interface IOdsSzdnSectionService extends IService<OdsSzdnSection> {
    /**
     * 查询路段信息
     *
     * @param id 路段信息ID
     * @return 路段信息
     */
    OdsSzdnSection selectOdsSzdnSectionById(String id);

    /**
     * 查询路段信息列表
     *
     * @param odsSzdnSection 路段信息
     * @return 路段信息集合
     */
    List<OdsSzdnSection> selectOdsSzdnSectionList(OdsSzdnSection odsSzdnSection);

}
