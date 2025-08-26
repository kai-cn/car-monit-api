package com.ruoyi.modules.vo.orders;

import lombok.Data;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/9/2 14:34
 * @Return
 */
@Data
public class OrderFlagVO {

    private boolean bmallOrderFlag;
    private boolean buyTryOrderFlag;
    private boolean codOrderFlag;
    private boolean consignmentOrderFlag;
    private boolean deliveryToStoreFlag;
    private boolean flowerStoreOrderFlag;
    private boolean globalBondedOrder;
    private boolean globalDirectOrder;
    private boolean goodsSourceGrayFlag;
    private boolean indexOrderFlag;
    private boolean jpControlOrderFlag;
    private boolean jycOrderFlag;
    private boolean ldpOrderFlag;
    private boolean mergeOrderFlag;
    private boolean partRefundOrderFlag;
    private boolean partialShipmentOrderFlag;
    private boolean specialOrderFlag;
    private boolean tiktokOrderFlag;
    private boolean zpjdOrderFlag;

}
