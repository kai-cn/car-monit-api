package com.ruoyi.modules.vo.sms;

import io.swagger.annotations.ApiModel;
import io.swagger.annotations.ApiModelProperty;
import lombok.Data;

import java.io.Serializable;

/**
 * 短信接口返回对象
 * @param
 */
@Data
@ApiModel(value = "短信一对一发送接口返回对象", description = "短信一对一发送接口返回对象")
public class MessageOneResultDataDetail implements Serializable {

    private static final long serialVersionUID = 1L;

    /**
     * 返回处理消息
     */
    @ApiModelProperty(value = "处理结果描述")
    private String message;

    /**
     * 返回代码
     */
    @ApiModelProperty(value = "返回代码")
    private Integer code;

    /**
     * 当code=0时，系统返回唯一消息Id
     */
    @ApiModelProperty(value = "当code=0时，系统返回唯一消息Id")
    private Long msgId;

    /**
     * 当code=0时，系统返回消耗计费总数
     */
    @ApiModelProperty(value = "当code=0时，系统返回消耗计费总数")
    private Integer smsCount;

    /**
     * 返回数据对象 data
     */
    @ApiModelProperty(value = "发送手机号码")
    private String phone;

}
