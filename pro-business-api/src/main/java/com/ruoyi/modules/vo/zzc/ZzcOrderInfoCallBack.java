package com.ruoyi.modules.vo.zzc;

import io.swagger.annotations.ApiModelProperty;
import io.swagger.models.auth.In;
import lombok.Data;
import lombok.experimental.Accessors;

import javax.validation.constraints.NotEmpty;
import java.math.BigDecimal;

/**
 * @Description: 单号宝请求参数类
 * @Author HuangJun
 * @Date 2024/4/22 14:02
 * @Return
 */
@Data
@Accessors(chain = true)
public class ZzcOrderInfoCallBack {

    @ApiModelProperty(value = "业务类型",notes = "业务类型：type=1 重量扣费，type=2 包裹状态，type=3退回件的超重扣费，type=4提前揽件仓库已打包礼品发出，type=5 提前揽件仓库已打包礼品发出，type=6 推送疑难件的信息，type=7 推送不取单号下单，然后更新新的中转单号，type=8 推送超重退回费用， price正数是退回，负数是扣除")
    @NotEmpty(message = "业务类型不能为空")
    private String type;

    @ApiModelProperty(value = "中转物流运单号")
    private String sendLogisticsNumber;


    @ApiModelProperty(value = "中转物流运单号")
    private String packDetail;


    @ApiModelProperty(value = "中转物流运单号")
    private BigDecimal price;


    @ApiModelProperty(value = "中转物流运单号")
    private BigDecimal weight;


    @ApiModelProperty(value = "是否礼品单：true/false")
    private Boolean lipin;


    @ApiModelProperty(value = "中转礼品单物流运单号")
    private String newSendLogisticsNumber;


    @ApiModelProperty(value = "订单状态int类型：1未到中转仓,2已到中转仓,3已打包转寄")
    private Integer packState;


    @ApiModelProperty(value = "中转仓新物流单号")
    private String logisticsNew;


    @ApiModelProperty(value = "备注：疑难件ID(123),请处理")
    private String remark;


    @ApiModelProperty(value = "中转仓单据主键")
    private String zzcId;
}


