package com.ruoyi.common.config.interceptor;

import com.alibaba.fastjson2.JSON;
import com.ruoyi.common.config.annotation.PermissionAnon;
import com.ruoyi.common.config.base.Result;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.method.HandlerMethod;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.ModelAndView;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.Objects;

/**
 * API 访问鉴权拦截器。
 *
 * <p>校验请求头中的共享令牌（默认 {@code X-API-Token}），未通过校验的请求返回 401。
 * 标注 {@link PermissionAnon} 的方法/类不做校验（仅用于健康检查等无敏感数据的端点）。</p>
 *
 * <p>配置项：</p>
 * <ul>
 *   <li>{@code api.security.enabled}：是否启用，默认 true</li>
 *   <li>{@code api.security.header}：令牌请求头名称，默认 X-API-Token</li>
 *   <li>{@code api.security.token}：令牌值，建议通过环境变量 API_SECURITY_TOKEN 注入</li>
 * </ul>
 *
 * <p>令牌未配置时采用“失败关闭”策略：所有受保护接口一律拒绝，避免配置遗漏导致匿名可访问。</p>
 */
@Slf4j
@Component
public class SecurityInterceptor implements HandlerInterceptor {

    @Value("${api.security.enabled:true}")
    private boolean enabled;

    @Value("${api.security.header:X-API-Token}")
    private String headerName;

    @Value("${api.security.token:}")
    private String expectedToken;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if (!enabled) {
            return true;
        }
        // 浏览器跨域预检请求不携带自定义头，直接放行
        if ("OPTIONS".equalsIgnoreCase(request.getMethod())) {
            return true;
        }
        if (isAnonymous(handler)) {
            return true;
        }
        String configuredPath = request.getRequestURI();
        if (expectedToken == null || expectedToken.trim().isEmpty()) {
            log.error("api.security.token 未配置，拒绝访问: {}", configuredPath);
            writeUnauthorized(response, "服务端未配置访问令牌");
            return false;
        }
        String provided = request.getHeader(headerName);
        if (provided == null || provided.isEmpty() || !constantTimeEquals(expectedToken, provided)) {
            log.warn("拒绝未授权访问: {} {}", request.getMethod(), configuredPath);
            writeUnauthorized(response, "未授权访问：No Permission 401");
            return false;
        }
        return true;
    }

    /**
     * 方法或类上标注 {@link PermissionAnon} 时视为匿名可访问。
     */
    private boolean isAnonymous(Object handler) {
        if (!(handler instanceof HandlerMethod)) {
            return false;
        }
        HandlerMethod handlerMethod = (HandlerMethod) handler;
        if (handlerMethod.getMethodAnnotation(PermissionAnon.class) != null) {
            return true;
        }
        PermissionAnon classAnnotation = handlerMethod.getBeanType().getAnnotation(PermissionAnon.class);
        return Objects.nonNull(classAnnotation);
    }

    /**
     * 定长比较，避免令牌比较被计时攻击利用。
     */
    private boolean constantTimeEquals(String expected, String provided) {
        byte[] expectedBytes = expected.getBytes(StandardCharsets.UTF_8);
        byte[] providedBytes = provided.getBytes(StandardCharsets.UTF_8);
        return MessageDigest.isEqual(expectedBytes, providedBytes);
    }

    private void writeUnauthorized(HttpServletResponse response, String message) throws Exception {
        response.setStatus(HttpStatus.UNAUTHORIZED.value());
        response.setCharacterEncoding("UTF-8");
        response.setContentType("application/json;charset=utf-8");
        Result<Void> result = new Result<>();
        result.setCode(HttpStatus.UNAUTHORIZED.value());
        result.setSuccess(false);
        result.setMessage(message);
        response.getWriter().println(JSON.toJSONString(result));
    }

    @Override
    public void postHandle(HttpServletRequest request, HttpServletResponse response, Object handler, ModelAndView modelAndView) throws Exception {
        // no-op
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) throws Exception {
        // no-op
    }
}
