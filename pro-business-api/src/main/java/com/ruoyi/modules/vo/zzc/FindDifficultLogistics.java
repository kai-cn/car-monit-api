package com.ruoyi.modules.vo.zzc;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

/**
 * @Description: 单号宝请求参数类
 * @Author HuangJun
 * @Date 2024/4/22 14:02
 * @Return
 */
@Data
@Accessors(chain = true)
public class FindDifficultLogistics {

    @ApiModelProperty(value = "查询接口里面返回的id")
    private String difficultId;

}


