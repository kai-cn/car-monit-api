package com.ruoyi.modules.vo.jd;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import javax.validation.constraints.NotEmpty;
import java.util.List;

/**
 * @Description: 订单列表查询接口参数
 * @Author HuangJun
 * @Date 2024/4/23 11:16
 * @Return
 */
@Data
public class OrderPage {

    @ApiModelProperty(value = "页码",required = true)
    @NotEmpty(message = "页码不能为空")
    private String current;

    @ApiModelProperty(value = "页条数：10 20 50",required = true)
    @NotEmpty(message = "页条数不能为空")
    private String pageSize;

    @ApiModelProperty(value = "查询订单tab标识：{近三个月订单：allOrders,待付款：notPay,待出库：waitOut,已出库：hadOut,已完成：completed,已取消：canceled,暂停订单：suspendAndLock,三个月前订单：threeMonthAgo}",required = true)
    @NotEmpty(message = "查询订单tab标识不能为空")
    private String orderTab;

    @ApiModelProperty(value = "排序方式[最新下单在下：orderDateAsc，最新下单在上：orderDateDesc，揽收超时在上：pickWarnDateAsc]",required = true)
    @NotEmpty(message = "排序方式不能为空")
    private String sortMode;

    @ApiModelProperty("订单编号")
    private String orderId;

    @ApiModelProperty("订单标签，非必填，传多个以逗号分隔[揽件预警：5，超时未揽件：6，催单：2，物流异常：9]")
    private List<String> orderTags;

    @ApiModelProperty("物流单号")
    private String logiNo;

    @ApiModelProperty("SKU编码")
    private String skuId;

    @ApiModelProperty("商品名称")
    private String skuName;

    @ApiModelProperty("客户姓名")
    private String consumerName;

    @ApiModelProperty("客户电话")
    private String consumerMobilePhone;

    @ApiModelProperty("下单时间:[\"2024-04-01 00:00:00\",\"2024-05-16 23:59:59\"]")
    private List<String> orderCreateDateRange;

    @ApiModelProperty("订单来源[落地配订单：10，服务履约订单：11，采购订单：13]")
    private String orderBusinessType;

    @ApiModelProperty("支付方式[货到付款：1，在线支付：4，公司转账：5]")
    private String paymentType;

    @ApiModelProperty("下单账号")
    private String userPin;

    @ApiModelProperty("配送方式[普通快递：67，消费者选择京配：68]")
    private String idSopShipmentType;

    @ApiModelProperty("仓库名称[商家全国仓：0，莆田赤阳道云仓1号库：800012417，莆田赤阳道云仓2号库：800012418，莆田赤阳道云仓3号库：800012419，莆田赤阳道云仓4号库：800012710，莆田赤阳道云仓5号库：800013226，莆田赤阳道云仓5号库：800013226，莆田赤阳道云仓6号库：800013478，莆田赤阳道云仓7号库：800013479]")
    private String storeId;

    @ApiModelProperty("收货地址[]")
    private String provinceIds;
}
