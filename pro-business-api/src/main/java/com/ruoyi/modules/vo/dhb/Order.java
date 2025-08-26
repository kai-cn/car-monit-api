package com.ruoyi.modules.vo.dhb;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/5/20 16:27
 * @Return
 */
@Data
@Accessors(chain = true)
public class Order{

    @ApiModelProperty(value = "收件地址(支持多中格式)必须包含省市区信息",required = true)
    @NotEmpty(message = "收件地址不能为空")
    private String address;

    @ApiModelProperty(value = "店铺订单号",required = true)
    @NotEmpty(message = "店铺订单号不能为空")
    private String shopOrderNo;

    @ApiModelProperty(value = "转寄快递单号(上游快递单号)[目前只支持快递 韵达,申通,中通, 圆通,极兔,邮政,韵达快运,京东,德邦,丰网,安能物流]")
    private String copyExpressNo;

    @ApiModelProperty(value = "上家快递公司代码（韵达[YUNDA]，申通[STO]，中通[ZTO],圆通[YTO]，极兔[JTSD]，邮政EMS[YZPY]，韵达快运[YDKY]，京东[JD]，德邦[DBL]，丰网[FWX]，安能物流[ANE]，中通快运[ZTOKY]）")
    private String copyExpressCode;

    @ApiModelProperty(value = "上家快递公司名称（韵达[YUNDA]，申通[STO]，中通[ZTO],圆通[YTO]，极兔[JTSD]，邮政EMS[YZPY]，韵达快运[YDKY]，京东[JD]，德邦[DBL]，丰网[FWX]，安能物流[ANE]，中通快运[ZTOKY]）")
    private String copyExpressName;

    @ApiModelProperty("商品名称，字符串长度<=8")
    private String goodsName;

    @ApiModelProperty("是否自动转同快递复制，默认 0， 如果给1值。 那么当上家快递单号是韵达或是中通的时候。会自动转出韵达复制韵达、中通复制中通类型的快递。（前提是需要在登录账号首页打开自动更换快递的开关）")
    private Long isAutoExpress;

    @ApiModelProperty("标记，可不填写")
    private String tag;

    @ApiModelProperty("可不填写")
    private String venderId;

    @ApiModelProperty(value = "店铺id")
    @NotNull(message = "店铺id不能为空")
    private String storeId;

    @ApiModelProperty(value = "店铺名称")
    @NotNull(message = "店铺名称不能为空")
    private String storeName;

    /**
     * 订单采购平台，pdd/tb/jd/tt/ks/dy/1688/tm/xhs   这9个固定的值，一次只能填一个值
     * 代码含义对应平台中文是【拼多多、淘宝、京东、淘特、快手、抖音、1688、天猫、小红书】
     */
    @ApiModelProperty(value = "订单采购平台")
    private String purchasePlatform;
    /**
     * 发件人电话，建议给商家的电话（该姓名会在快递面单的发件人号码栏）方便收件人直接联系到店铺商家
     */
    @ApiModelProperty(value = "发件人电话")
    private String senderMobile;
    /**
     * 发件人姓名，建议给商家的名称（该姓名会在快递面单的发件人栏）
     */
    @ApiModelProperty(value = "发件人姓名")
    private String senderName;
    /**
     * 店铺唯一标识(长度60)，订单所属店铺的唯一标识（在你们的唯一标识，不是单号宝）
     */
    @ApiModelProperty(value = "店铺唯一标识")
    private String shopUuid;

    /**
     * 用户唯一标识(长度60)，订单所属用户的唯一标识（在你们系统的唯一标识，不是单号宝）
     */
    @ApiModelProperty(value = "用户唯一标识")
    private String userUuid;
}
