package com.ruoyi.modules.vo.ems;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import javax.validation.constraints.NotEmpty;
import java.util.List;

/**
 * @Description: 畅邮宝API调用接口参数类
 * @Author HuangJun
 * @Date 2024/4/22 14:02
 * @Return
 */
@Data
@Accessors(chain = true)
public class EmsRequestModel {
    private String appKey;
    private String appSecret;
    private String timeStamp;
    private List<EmsOrderModel> orderList;

    @Data
    @Accessors(chain = true)
    public static class EmsOrderModel {
        @ApiModelProperty(value = "快递id",required = true)
        @NotEmpty(message = "快递id不能为空")
        private String kdId;

        //订单编号 -- 是否必填，是
        @ApiModelProperty(value = "订单编号",required = true)
        @NotEmpty(message = "订单编号不能为空")
        private String orderSn;

        //订单来源（1 淘宝 2 拼多多 3 京东 4 抖音） -- 是否必填，是
        @ApiModelProperty(value = "订单编号",required = true)
        @NotEmpty(message = "订单编号不能为空")
        private String platForm;

        //运单号 -- 是否必填，是
        @ApiModelProperty(value = "运单号",required = true)
        @NotEmpty(message = "运单号不能为空")
        private String kuaidiSn;

        //发件人姓名 -- 是否必填，是
        @ApiModelProperty(value = "发件人姓名",required = true)
        @NotEmpty(message = "发件人姓名不能为空")
        private String sendName;

        //发件人联系方式 -- 是否必填，是
        @ApiModelProperty(value = "发件人联系方式",required = true)
        @NotEmpty(message = "发件人联系方式不能为空")
        private String sendMobile;

        //发件人省份 -- 是否必填，是
        @ApiModelProperty(value = "发件人省份",required = true)
        @NotEmpty(message = "发件人省份不能为空")
        private String sendProvince;

        //发件人市区 -- 是否必填，是
        @ApiModelProperty(value = "发件人市区",required = true)
        @NotEmpty(message = "发件人市区不能为空")
        private String sendCity;

        //发件人区/街道 -- 是否必填，是
        @ApiModelProperty(value = "发件人区/街道",required = true)
        @NotEmpty(message = "发件人区/街道不能为空")
        private String sendDistrict;

        //发件人详细地址 -- 是否必填，是
        @ApiModelProperty(value = "发件人详细地址",required = true)
        @NotEmpty(message = "发件人详细地址不能为空")
        private String sendAddress;

        //收件人姓名 -- 是否必填，是
        @ApiModelProperty(value = "收件人姓名",required = true)
        @NotEmpty(message = "收件人姓名不能为空")
        private String recName;

        //收件人联系方式 -- 是否必填，是
        @ApiModelProperty(value = "收件人联系方式",required = true)
        @NotEmpty(message = "收件人联系方式不能为空")
        private String recMobile;

        //收货人省份 -- 是否必填，是
        @ApiModelProperty(value = "收货人省份",required = true)
        @NotEmpty(message = "收货人省份不能为空")
        private String recProvince;

        //收货人市 -- 是否必填，是
        @ApiModelProperty(value = "收货人市",required = true)
        @NotEmpty(message = "收货人市不能为空")
        private String recCity;

        //收货人区/街道 -- 是否必填，是
        @ApiModelProperty(value = "收货人区/街道",required = true)
        @NotEmpty(message = "收货人区/街道不能为空")
        private String recDistrict;

        //收货人详细地址 -- 是否必填，是
        @ApiModelProperty(value = "收货人详细地址",required = true)
        @NotEmpty(message = "收货人详细地址不能为空")
        private String recAddress;

        //商品名称 -- 是否必填，是
        @ApiModelProperty(value = "商品名称",required = true)
        @NotEmpty(message = "商品名称不能为空")
        private String goodsName;

        //商品编码 -- 是否必填，否
        @ApiModelProperty("商品编码，有则需填")
        private String goodsId;

        //商品规格 -- 是否必填，否
        @ApiModelProperty("商品规格，有则需填")
        private String skuId;

        //商品重量 -- 是否必填，否
        @ApiModelProperty("商品重量，有则需填")
        private String goodsWeight;

        //商品单价 -- 是否必填，否
        @ApiModelProperty("商品单价，有则需填")
        private String orderPrice;

        //商品数量 -- 是否必填，否
        @ApiModelProperty("商品数量，有则需填")
        private String goodsNumber;

        //打印数据 -- 是否必填，否
        @ApiModelProperty("打印数据")
        private String printData;

        //店铺名称 -- 是否必填，否
        @ApiModelProperty("店铺名称")
        private String shopName;

        //上家快递单号 -- 是否必填，否
        @ApiModelProperty("上家快递单号")
        private String expressSn;

        //平台订单号，（店铺名称，上家快递单号，平台订单号都传了，面单上会备注上） -- 是否必填，否
        @ApiModelProperty("平台订单号")
        private String shopOrder;

     /* EmsRequestModel.EmsOrderModel emsOrderModel = new EmsRequestModel.EmsOrderModel();
        emsOrderModel.setKdId("123131212");
        emsOrderModel.setOrderSn("13231313");
        emsOrderModel.setPlatForm("1");
        emsOrderModel.setKuaidiSn("12313");
        emsOrderModel.setSendName("金三帅");
        emsOrderModel.setSendMobile("131231");
        emsOrderModel.setSendProvince("广东");
        emsOrderModel.setSendCity("广州市");
        emsOrderModel.setSendDistrict("白云区");
        emsOrderModel.setSendAddress("广东省广州市白云区钟落潭镇广从五路111号");
        emsOrderModel.setRecName("陈晓庆");
        emsOrderModel.setRecMobile("19532004199-4514");
        emsOrderModel.setRecProvince("四川");
        emsOrderModel.setRecCity("成都市");
        emsOrderModel.setRecDistrict("锦江区");
        emsOrderModel.setRecAddress("四川成都市锦江区三圣街道锦江区");
        emsOrderModel.setGoodsName("湿纸巾");
        emsOrderModel.setGoodsId("899");
        //emsOrderModel.setSkuId();
        emsOrderModel.setGoodsWeight("40.00");
        emsOrderModel.setOrderPrice("1.46");
        emsOrderModel.setGoodsNumber("1");*/
    }
}


