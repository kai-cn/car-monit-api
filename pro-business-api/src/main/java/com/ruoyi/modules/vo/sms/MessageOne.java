package com.ruoyi.modules.vo.sms;

import io.swagger.annotations.ApiModelProperty;
import lombok.Data;
import lombok.experimental.Accessors;

import javax.validation.constraints.NotEmpty;

@Data
@Accessors(chain = true)
public class MessageOne {
    @ApiModelProperty(value = "帐号用户名",required = true)
    @NotEmpty(message = "手机号不能为空")
    private String phone;

    @ApiModelProperty(value = "帐号用户名",required = true)
    @NotEmpty(message = "短信内容不能为空")
    private String content;

    @ApiModelProperty(value = "可选，附带通道扩展码")
    private String extcode;

    @ApiModelProperty(value = "用户回传数据，最大长度64。用户若传递此参数将在回执推送时回传给用户。")
    private String callData;
}
