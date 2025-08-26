package com.ruoyi.modules.mapper;

import com.ruoyi.modules.entity.EcCostSz;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 费用设置Mapper接口
 *
 * @author ruoyi
 * @date 2024-07-09
 */
@Repository
public interface EcCostSzMapper {
    /**
     * 查询费用设置
     *
     * @param id 费用设置ID
     * @return 费用设置
     */
    EcCostSz selectEcCostSzById(String id);

    /**
     * 查询费用设置列表
     *
     * @param ecCostSz 费用设置
     * @return 费用设置集合
     */
    List<EcCostSz> selectEcCostSzList(EcCostSz ecCostSz);

    /**
     * 新增费用设置
     *
     * @param ecCostSz 费用设置
     * @return 结果
     */
    int insertEcCostSz(EcCostSz ecCostSz);

    /**
     * 修改费用设置
     *
     * @param ecCostSz 费用设置
     * @return 结果
     */
    int updateEcCostSz(EcCostSz ecCostSz);

    /**
     * 删除费用设置
     *
     * @param id 费用设置ID
     * @return 结果
     */
    int deleteEcCostSzById(String id);

    /**
     * 批量删除费用设置
     *
     * @param ids 需要删除的数据ID
     * @return 结果
     */
    int deleteEcCostSzByIds(String[] ids);

    /**
     * 修改费用设置
     *
     * @param ecCostSz 费用设置
     * @return 结果
     */
    int isExists(EcCostSz ecCostSz);
}
