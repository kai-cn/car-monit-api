package com.ruoyi.modules.service.impl;

import com.baomidou.mybatisplus.extension.service.impl.ServiceImpl;
import com.ruoyi.modules.entity.CategoryPointsInfo;
import com.ruoyi.modules.mapper.CategoryPointsInfoMapper;
import com.ruoyi.modules.service.ICategoryPointsInfoService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import java.util.List;

/**
 * 类目扣点管理Service业务层处理
 *
 * @author huangjun
 * @date 2024-06-24
 */
@Slf4j
@Service
public class CategoryPointsInfoServiceImpl extends ServiceImpl<CategoryPointsInfoMapper, CategoryPointsInfo> implements ICategoryPointsInfoService {
    @Autowired
    private CategoryPointsInfoMapper categoryPointsInfoMapper;


    /**
     * 查询类目扣点管理
     *
     * @param id 类目扣点管理ID
     * @return 类目扣点管理
     */
    @Override
    public CategoryPointsInfo selectCategoryPointsInfoById(String id) {
        return categoryPointsInfoMapper.selectCategoryPointsInfoById(id);
    }

    /**
     * 查询类目扣点管理列表
     *
     * @param categoryPointsInfo 类目扣点管理
     * @return 类目扣点管理
     */
    @Override
    public List<CategoryPointsInfo> selectCategoryPointsInfoList(CategoryPointsInfo categoryPointsInfo) {
        return categoryPointsInfoMapper.selectCategoryPointsInfoList(categoryPointsInfo);
    }
}
