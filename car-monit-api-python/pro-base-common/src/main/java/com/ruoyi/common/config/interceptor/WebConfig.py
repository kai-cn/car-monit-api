# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.interceptor.WebConfig

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/interceptor/WebConfig.java

【Java→Python】重要说明：本文件在 Java 源码中**整体被 /* ... */ 注释掉**，
因此 SecurityInterceptor 实际并未通过 WebMvcConfigurer 注册到 "/base/**" 路径上。

为保证“一比一像素级重构”，Python 侧同样保持“不生效”，仅保留占位符。

--- 原 Java 代码（被注释） -------------------------------------------------
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Autowired
    private SecurityInterceptor securityInterceptor;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(securityInterceptor)
                .addPathPatterns("/base/**");
    }
}

--- 对应的 Python 写法（同样不启用，仅作对照保留） -------------------------
# Spring MVC 的 HandlerInterceptor → FastAPI/Flask 的中间件或依赖项；
# 注册方式差异很大（Spring 用 registry.addInterceptor + Ant 路径，Python 框架用
# app.before_request / add_middleware），因此即使启用也需要按目标框架重写，
# 而非逐行翻译。
class WebConfig:
    def addInterceptors(self, registry) -> None:
        registry.addInterceptor(self.securityInterceptor).addPathPatterns("/base/**")
--------------------------------------------------------------------------
"""
from __future__ import annotations

# 与 Java 一致：该类不生效。占位符防止 import 报错。
WebConfig = None
