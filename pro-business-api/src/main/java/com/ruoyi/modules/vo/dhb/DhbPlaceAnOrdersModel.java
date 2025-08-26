package com.ruoyi.modules.vo.dhb;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;
import java.util.List;

/**
 * @Description: 单号宝请求参数类
 * @Author HuangJun
 * @Date 2024/4/22 14:02
 * @Return
 */
@Data
@Accessors(chain = true)
public class DhbPlaceAnOrdersModel {

    @ApiModelProperty(value = "账号：前端不传",hidden = true)
    private String appKey;

    @ApiModelProperty(value = "签名：前端不传",hidden = true)
    private String sign;

    @ApiModelProperty(value = "商家店铺所属的电商平台，tb,jd,pdd,dy,ks,xhs【固定值，如果给值jd则出单号就是京东的无界面单】",required = true)
    @NotEmpty(message = "所属的电商平台不能为空")
    private String buyPlatform;

    /**
     * 固定值，能传的值在下面中括号
     * 【YUNDA，2_YD， 2_ZT，3_DG_EMS_JCB，3_DG_EMS_XSD，3_DG_EMS_RZJ 】
     * 每个值的说明：
     * YUNDA : 韵达延迟单（最开始的韵达单）
     * 2_YD：韵达复制韵达
     * 2_ZT：中通复制中通
     * 3_DG_EMS_JCB：东莞邮政礼品单-洁厕宝
     * 3_DG_EMS_XSD：东莞邮政礼品单-小苏打
     * 3_DG_EMS_RZJ：东莞邮政礼品单-柔纸巾
     */
    @ApiModelProperty(value = "快递编码，请填写(YUNDA)【目前只支持韵达】",required = true)
    @NotEmpty(message = "快递编码不能为空")
    private String expressCode;

    @ApiModelProperty(value = "回调通知地址")
    private String notifyUrl;

    @ApiModelProperty(value = "订单集合，(不参与签名)",required = true)
    @NotNull(message = "订单集合不能为空")
    private List<Order> orders;

}


