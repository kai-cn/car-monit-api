package com.ruoyi.modules.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.modules.entity.CategoryPointsInfo;
import org.apache.ibatis.annotations.Param;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 类目扣点管理Mapper接口
 *
 * @author huangjun
 * @date 2024-06-24
 */
@Repository
public interface CategoryPointsInfoMapper extends BaseMapper<CategoryPointsInfo> {
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

    /**
     * 新增类目扣点管理
     *
     * @param categoryPointsInfo 类目扣点管理
     * @return 结果
     */
    int insertCategoryPointsInfo(CategoryPointsInfo categoryPointsInfo);

    /**
     * 批量新增评议领导信息
     *
     * @param list 评议领导信息
     * @return 结果
     */
    int batchedSaveCategoryPoints(@Param("list") List<CategoryPointsInfo> list);

    /**
     * 修改类目扣点管理
     *
     * @param categoryPointsInfo 类目扣点管理
     * @return 结果
     */
    int updateCategoryPointsInfo(CategoryPointsInfo categoryPointsInfo);

    /**
     * 删除类目扣点管理
     *
     * @param id 类目扣点管理ID
     * @return 结果
     */
    int deleteCategoryPointsInfoById(String id);

    /**
     * 批量删除类目扣点管理
     *
     * @param ids 需要删除的数据ID
     * @return 结果
     */
    int deleteCategoryPointsInfoByIds(String[] ids);
}
