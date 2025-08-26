package com.ruoyi.modules.mapper;


import com.ruoyi.modules.entity.EcBillingStatement;
import org.springframework.stereotype.Repository;

import java.util.List;

/**
 * 账单流水Mapper接口
 *
 * @author ruoyi
 * @date 2024-07-04
 */
@Repository
public interface EcBillingStatementMapper {
    /**
     * 查询账单流水
     *
     * @param id 账单流水ID
     * @return 账单流水
     */
    EcBillingStatement selectEcBillingStatementById(String id);

    /**
     * 查询账单流水列表
     *
     * @param ecBillingStatement 账单流水
     * @return 账单流水集合
     */
    List<EcBillingStatement> selectEcBillingStatementList(EcBillingStatement ecBillingStatement);

    /**
     * 新增账单流水
     *
     * @param ecBillingStatement 账单流水
     * @return 结果
     */
    int insertEcBillingStatement(EcBillingStatement ecBillingStatement);

    /**
     * 修改账单流水
     *
     * @param ecBillingStatement 账单流水
     * @return 结果
     */
    int updateEcBillingStatement(EcBillingStatement ecBillingStatement);

    /**
     * 删除账单流水
     *
     * @param id 账单流水ID
     * @return 结果
     */
    int deleteEcBillingStatementById(String id);

}
