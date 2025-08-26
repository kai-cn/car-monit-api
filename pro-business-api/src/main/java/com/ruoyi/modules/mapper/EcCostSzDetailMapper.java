package com.ruoyi.modules.mapper;

import com.ruoyi.modules.entity.EcCostSzDetail;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 扣费费用明细Mapper接口
 *
 * @author ruoyi
 * @date 2024-08-16
 */
@Repository
public interface EcCostSzDetailMapper  {

    /**
     * 查询扣费费用明细列表
     *
     * @param ecCostSzDetail 扣费费用明细
     * @return 扣费费用明细集合
     */
    List<EcCostSzDetail> selectEcCostSzDetailList(EcCostSzDetail ecCostSzDetail);

}
