package com.ruoyi.common.config.interceptor;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 注册 API 鉴权拦截器。所有 HTTP 接口默认要求携带访问令牌，健康检查等端点除外。
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Autowired
    private SecurityInterceptor securityInterceptor;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(securityInterceptor)
                .addPathPatterns("/**")
                .excludePathPatterns("/actuator/health", "/actuator/health/**", "/actuator/info", "/error");
    }
}
