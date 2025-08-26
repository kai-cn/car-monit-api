package com.ruoyi.common.config.annotation;

import java.lang.annotation.*;

/**
 *  类描述:  自定义权限拦截注解
 *  校验规则 apiAuth: 权限拦截标识  verifyFlag 方法描述: 应用校验标识
 * 作    者： 黄君
 * 日    期： 2020-03-17
 */
@Target({ElementType.TYPE, ElementType.METHOD})
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface PermissionAnon {

}
