package com.ruoyi.base.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure;
import org.apache.ibatis.annotations.MapKey;
import org.apache.ibatis.annotations.Param;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Map;

/**
 * 省界称重Mapper接口
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Repository
public interface OdsSzdnProvinceBorderVehicleWeightNewstructureMapper extends BaseMapper<OdsSzdnProvinceBorderVehicleWeightNewstructure> {
    /**
     * 查询省界称重
     *
     * @param dataSource 省界称重ID
     * @return 省界称重
     */
    OdsSzdnProvinceBorderVehicleWeightNewstructure selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(String dataSource);

    /**
     * 查询省界称重列表
     *
     * @param odsSzdnProvinceBorderVehicleWeightNewstructure 省界称重
     * @return 省界称重集合
     */
    List<OdsSzdnProvinceBorderVehicleWeightNewstructure> selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(OdsSzdnProvinceBorderVehicleWeightNewstructure odsSzdnProvinceBorderVehicleWeightNewstructure);

    /**
     * 查询省界称重 : 通过IDS查询
     *
     * @return 省界称重
     */
    List<OdsSzdnProvinceBorderVehicleWeightNewstructure> selectOdsSzdnProvinceBorderVehicleWeightNewstructureByUuidList(@Param("uuidList") List<String> uuidList);
}
