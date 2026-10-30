# -*- coding: utf-8 -*-
"""com.ruoyi.common.config.interceptor.SecurityInterceptor

源文件：pro-base-common/src/main/java/com/ruoyi/common/config/interceptor/SecurityInterceptor.java

【Java→Python】重要说明：本文件在 Java 源码中**整体被 /* ... */ 注释掉**，
且源码里还嵌套了 ``/** ... */`` 的 Javadoc（Java 不允许嵌套块注释，
这也是它被整体注释的原因之一）。它不会注册为拦截器，也不会生效。

为保证“一比一像素级重构”，Python 侧同样保持“不生效”：
类体全部保留在下面的注释块中，模块只提供占位符。

--- 原 Java 逻辑摘要（被注释） -------------------------------------------
preHandle():
  1) 调用 hasPermission()，无权限时：
     - 打 error 日志 "Responding with unauthorized error. Message:{}, url:{}"
     - 响应 401 + UTF-8 + application/json;charset=utf-8
     - 写回 Result{code=401, success=false, message="未授权访问：No Permission 401"}
  2) 有权限返回 true

hasPermission():
  - handler 是 HandlerMethod 时：
    - 取方法上的 @PermissionAnon，为空再取类上的；命中 → true
    - 否则取方法上的 @ValidHeader：
        * header 名 == "d-anno"   ：值必须等于 Constants.D_ANNO，否则 401
        * header 名 == "d-cookie" ：值非空，否则 401
  - 其余情况 → true

--- 对应的 Python 写法（同样不启用，仅作对照保留） -------------------------
class SecurityInterceptor:            # implements HandlerInterceptor
    def preHandle(self, request, response, handler) -> bool:
        permission_valid = self.hasPermission(request, response, handler)
        if not permission_valid:
            logger.error("Responding with unauthorized error. Message:{}, url:{}",
                         "没有API访问权限", request.getRequestURI())
            response.setStatus(HttpStatus.UNAUTHORIZED.value())
            response.setCharacterEncoding("UTF-8")
            response.setContentType("application/json;charset=utf-8")
            result = Result()
            result.setCode(HttpStatus.UNAUTHORIZED.value())
            result.setSuccess(False)
            result.setMessage("未授权访问：No Permission 401")
            response.getWriter().println(JSON.toJSONString(result))
            return False
        return True

    def hasPermission(self, request, response, handler) -> bool:
        # HandlerMethod → 函数对象；getAnnotation → 读取函数属性 __permission_anon__
        # 对应 Java 的 handler instanceof HandlerMethod
        ...
--------------------------------------------------------------------------
"""
from __future__ import annotations

# 与 Java 一致：该类不生效。占位符防止 import 报错。
SecurityInterceptor = None
