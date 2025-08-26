package com.ruoyi.modules.vo.dhb;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import javax.validation.Valid;
import javax.validation.constraints.NotEmpty;
import javax.validation.constraints.NotNull;

/**
 * @Description: 单号宝请求参数类
 * @Author HuangJun
 * @Date 2024/4/22 14:02
 * @Return
 */
@Data
@Accessors(chain = true)
public class DhbFormCallBack {
/*    {
        "code": 0,
        "data": {
            "account": "15622845784",
            "copyExpressNo": "",
            "expressNo": "4281102791856352",
            "msgContent": "客户要求我司联系派件员送货上门并回电",
            "shopOrderNo": "38724fd93f2851"
        },
        "message": "success",
        "sign": "2f1080de9275d97c2af082fc81380192"
    }*/

    @ApiModelProperty(value = "标识：0 成功,  其他皆是错误",required = true)
    @NotNull(message = "标识不能为空")
    private long code;

    @ApiModelProperty(value = "参数对象",required = true)
    @Valid
    @NotNull(message = "参数对象不能为空")
    private ComplaintFormModel data;

    @ApiModelProperty(value = "响应信息，正常success  其他是错误信息",required = true)
    @NotEmpty(message = "响应信息不能为空")
    private String message;

    @ApiModelProperty(value = "签名",required = true)
    @NotEmpty(message = "签名不能为空")
    private String sign;

}


