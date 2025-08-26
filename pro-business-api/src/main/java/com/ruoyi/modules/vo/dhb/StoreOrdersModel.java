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
public class StoreOrdersModel {

    @ApiModelProperty(value = "店铺id")
    @NotNull(message = "店铺id不能为空")
    private String storeId;

    @ApiModelProperty(value = "店铺名称")
    @NotNull(message = "店铺名称不能为空")
    private String storeName;
}


