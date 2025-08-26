package com.ruoyi.modules.vo.jd;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;
import java.util.List;

/**
 * @Description: 商家备注参数类
 * @Author HuangJun
 * @Date 2024/4/23 11:13
 * @Return
 */
@Data
public class VenderRemarkBatch {

    @ApiModelProperty(value = "订单编号",required = true)
    @NotNull(message = "订单id集合不能为空")
    private List<String> orderId;

    @ApiModelProperty(value = "标记：012345",required = true)
    @NotNull(message = "标记不能为空")
    private Integer level;

    @ApiModelProperty(value = "备注信息",required = true)
    @NotEmpty(message = "备注信息不能为空")
    private String remark;

}
