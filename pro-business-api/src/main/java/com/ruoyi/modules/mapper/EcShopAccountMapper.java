package com.ruoyi.modules.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.ruoyi.modules.entity.EcShopAccount;
import org.springframework.stereotype.Repository;

/**
 * 增值账号Mapper接口
 *
 * @author ruoyi
 * @date 2024-07-04
 */
@Repository
public interface EcShopAccountMapper  extends BaseMapper<EcShopAccount> {

    /**
     * 查询增值账号
     *
     * @param id 增值账号ID
     * @return 增值账号
     */
    EcShopAccount selectEcShopAccountById(String id);

    /**
     * 修改增值账号
     *
     * @param ecShopAccount 增值账号
     * @return 结果
     */
    int updateEcShopAccountMonery(EcShopAccount ecShopAccount);


}
