package com.ruoyi.base.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.base.domain.OdsSzdnToll;
import com.ruoyi.common.core.domain.AjaxResult;

import java.util.List;

/**
 * 收费站基础信息Service接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
public interface IOdsSzdnTollService extends IService<OdsSzdnToll> {
    /**
     * 查询收费站基础信息
     *
     * @param id 收费站基础信息ID
     * @return 收费站基础信息
     */
    OdsSzdnToll selectOdsSzdnTollById(String id);

    /**
     * 查询收费站基础信息列表
     *
     * @param odsSzdnToll 收费站基础信息
     * @return 收费站基础信息集合
     */
    List<OdsSzdnToll> selectOdsSzdnTollList(OdsSzdnToll odsSzdnToll);
}
