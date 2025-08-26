package com.ruoyi.modules.vo.ems;

import com.alibaba.fastjson.JSONObject;
import lombok.Data;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/4/22 14:38
 * @Return
 */
@Data
public class EmsResponseModel {
    private String code;
    private String msg;
    private Object data;
}
