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
public class DhbUserModel {

    @ApiModelProperty(value = "账号：前端不传",hidden = true)
    private String appKey;

    @ApiModelProperty(value = "10位时间戳，跟当前时间的差值不能超过10分钟")
    private Long st;

    @ApiModelProperty(value = "签名：前端不传",hidden = true)
    private String sign;

}


