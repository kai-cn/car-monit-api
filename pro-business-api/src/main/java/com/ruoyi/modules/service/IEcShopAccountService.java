package com.ruoyi.modules.service;

import com.baomidou.mybatisplus.extension.service.IService;
import com.ruoyi.common.config.base.Result;
import com.ruoyi.modules.config.enums.CostTypeEnum;
import com.ruoyi.modules.entity.EcShopAccount;

import java.math.BigDecimal;
import java.util.Map;


public interface IEcShopAccountService extends IService<EcShopAccount> {

    EcShopAccount selectEcShopAccountBO(String bussId, String bussType);

    /**
     * 扣款之前校验：成功返回账号信息  失败返回错误信息
     *
     * @param costType 费用类型
     * @param bussId   业务ID 账号ID 或者 店铺ID
     * @param bussId   租户ID
     * @param bussType 1账号 2是店铺
     * @param quantity 数量
     * @param map      其他参数
     * @return
     */
    Result checkPrePay(String costType, String bussId, String bussType, Long tenantId, int quantity, Map map);

    /**
     * 执行扣款
     *
     * @param costType  费用类型
     * @param orderId   订单ID
     * @param storeId   店铺id
     * @param storeName 店铺名称
     * @param remark   备注
     * @param account   店铺绑定的账号对象
     * @param map   其他参数
     * @return
     */
    Result doPay(String costType, String orderId, String storeId, String storeName, String remark, EcShopAccount account, Map map);

    /**
     * 退款 ：根据订单id和业务退款
     *
     * @param paraAccount 增值账号
     * @param costTypeEnum 增值账号
     * @return 结果
     */
    Result doRefund(EcShopAccount paraAccount, CostTypeEnum costTypeEnum);

    /**
     * 无明细退款
     *
     * @param paraAccount 增值账号
     * @param costTypeEnum 增值账号
     * @return 结果
     */
    Result doRefundNoDetail(EcShopAccount paraAccount, CostTypeEnum costTypeEnum, BigDecimal resultCostMoney,String msg);

}
