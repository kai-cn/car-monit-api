package com.ruoyi.modules.vo.kdn;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import java.util.List;

/**
 * @Description: 快递鸟API调用接口参数类
 * @Author HuangJun
 * @Date 2024/4/22 14:02
 * @Return
 */
@Data
@Accessors(chain = true)
public class KdnResponseModel {

    @ApiModelProperty(value = "用户ID",required = true)
    private String EBusinessID;

    @ApiModelProperty(value = "快递公司编码")
    private String ShipperCode;

    @ApiModelProperty(value = "快递单号")
    private String LogisticCode;

    @ApiModelProperty(value = "成功与否(true/false)")
    private String Success;

    @ApiModelProperty(value = "普通物流状态：0-暂无轨迹信息,1-已揽收,2-在途中,3-签收,4-问题件,5-转寄,6-清关")
    private String Reason;

    @ApiModelProperty(value = "订单编号")
    private String State;

    @ApiModelProperty(value = "订单编号",required = true)
    private String OrderCode;

    @ApiModelProperty(value = "轨迹集合")
    private List<TracesList> Traces;

    @Data
    @Accessors(chain = true)
    public static class TracesList {
        @ApiModelProperty(value = "轨迹发生时间,示例：2021-01-01 09:00:00")
        private String AcceptTime;

        @ApiModelProperty(value = "轨迹描述")
        private String AcceptStation;
    }
}


