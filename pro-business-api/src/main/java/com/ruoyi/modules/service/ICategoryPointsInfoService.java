package com.ruoyi.modules.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.modules.entity.CategoryPointsInfo;

import java.util.List;

/**
 * 类目扣点管理Service接口
 *
 * @author huangjun
 * @date 2024-06-24
 */
public interface ICategoryPointsInfoService extends IService<CategoryPointsInfo> {
    /**
     * 查询类目扣点管理
     *
     * @param id 类目扣点管理ID
     * @return 类目扣点管理
     */
    CategoryPointsInfo selectCategoryPointsInfoById(String id);

    /**
     * 查询类目扣点管理列表
     *
     * @param categoryPointsInfo 类目扣点管理
     * @return 类目扣点管理集合
     */
    List<CategoryPointsInfo> selectCategoryPointsInfoList(CategoryPointsInfo categoryPointsInfo);

}
