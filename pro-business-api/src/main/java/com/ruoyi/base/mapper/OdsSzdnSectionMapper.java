package com.ruoyi.base.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.base.domain.OdsSzdnSection;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 路段信息Mapper接口
 *
 * @author ruoyi
 * @date 2025-08-29
 */
@Repository
public interface OdsSzdnSectionMapper extends BaseMapper<OdsSzdnSection> {
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
