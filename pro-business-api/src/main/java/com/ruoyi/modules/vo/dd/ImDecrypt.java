package com.ruoyi.modules.vo.dd;

import lombok.Data;
import java.util.List;

/**
 * @Description: 解密请求参数类
 * @Author HuangJun
 * @Date 2024/5/15 10:31
 * @Return
 */
@Data
public class ImDecrypt {

    //解密key
    private List<String> encryKeys;

    //新加密
    private String encryptNew = "true";

    //校验类型
    private Integer authType = 4;

    //参数
    private ImParams params;

}
