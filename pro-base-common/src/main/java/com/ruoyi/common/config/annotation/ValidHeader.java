package com.ruoyi.common.config.annotation;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * @Description:
 * @Author HuangJun
 * @Date 2024/5/15 17:10
 * @Return
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface ValidHeader {

    //请求头名称
    String[] value();

    //返回messages
    String message() default "Header parameter is empty";
}
