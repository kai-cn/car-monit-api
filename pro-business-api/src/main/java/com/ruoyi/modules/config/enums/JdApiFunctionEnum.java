package com.ruoyi.modules.config.enums;

/**
 * @Description: 京东API接口方法详情
 * @Author HuangJun
 * @Date 2024/5/16 10:07
 * @Return
 */
public enum JdApiFunctionEnum {

    获取订单列表信息("dsm.order.manage.orderlist.queryOrderPage"),
    获取订单物流信息("dsm.order.manage.orderdetail.getOrderTrack"),
    设置及修改商家备注("dsm.order.manage.orderdetail.submitVenderRemark"),
    批量设置及修改商家备注("dsm.order.manage.orderlist.batchSubmitVenderRemark"),
    普通发货("dsm.order.manage.OrderLogisticsReadService.maliciousResellingCheck"),
    电子面单发货("dsm.order.manage.orderOutShipService.batchOutShip"),
    获取隐藏的地址及电话("dsm.order.manage.PhoneVirtualNumberService.getDesensitizationInfo"),
    获取商品信息("dsm.wareshopv2.ware.wareListService.queryWareList"),
    查询京东类目信息("dsm.wareshopv2.ware.CategoryService.getChildCategory");

    private String api;

    private JdApiFunctionEnum(String api){
        this.api = api;
    }

    public String getJdApiFunction() {
        return api;
    }

}
