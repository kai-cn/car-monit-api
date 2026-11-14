package com.ruoyi.base.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.HandlerInterceptor;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.nio.charset.StandardCharsets;

/**
 * 内部端点防护：V3 运维端点（/api/v3/**）与导出任务端点（/api/v1/large/export/**）
 * 可切换查询引擎、覆盖 ES 模板、删除孤儿文档、触发全量回灌，并可直接下载全字段导出文件。
 * 本工程 SecurityInterceptor/WebConfig 长期被注释，等于无鉴权，因此这里按端点做最小闭环：
 *
 * <ul>
 *   <li>配置 {@code traffic.security.internal-token} 后，所有受保护端点必须携带
 *       {@code X-Internal-Token}，常量时间比较，错误返回 403；</li>
 *   <li>未配置令牌时只允许本机回环调用（单机联调/本机 backend），非回环一律 403；</li>
 *   <li>多机部署必须显式配置同一令牌，由 backend 与运维脚本注入请求头。</li>
 * </ul>
 *
 * 说明：这只是服务间/运维面的最小边界，不替代设计文档 §5.7 的租户权限模型；
 * 生产仍应叠加内网绑定、网关认证与审计。
 */
@Configuration
public class InternalEndpointGuardConfig implements WebMvcConfigurer {

    public static final String TOKEN_HEADER = "X-Internal-Token";

    private final String token;

    public InternalEndpointGuardConfig(@Value("${traffic.security.internal-token:}") String token) {
        this.token = token == null ? "" : token.trim();
    }

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new HandlerInterceptor() {
            @Override
            public boolean preHandle(HttpServletRequest request, HttpServletResponse response,
                                     Object handler) throws Exception {
                if (!token.isEmpty()) {
                    String provided = request.getHeader(TOKEN_HEADER);
                    if (provided != null && constantTimeEquals(token, provided.trim())) {
                        return true;
                    }
                    return deny(response, "内部端点需要有效的 " + TOKEN_HEADER);
                }
                String remote = request.getRemoteAddr();
                if ("127.0.0.1".equals(remote) || "::1".equals(remote)
                        || "0:0:0:0:0:0:0:1".equals(remote)) {
                    return true;
                }
                return deny(response, "内部端点仅允许本机调用，请配置 traffic.security.internal-token");
            }
        }).addPathPatterns("/api/v3/**", "/api/v1/large/export/**");
    }

    private static boolean deny(HttpServletResponse response, String message) throws Exception {
        response.setStatus(HttpServletResponse.SC_FORBIDDEN);
        response.setCharacterEncoding(StandardCharsets.UTF_8.name());
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write("{\"code\":403,\"message\":\"" + message + "\"}");
        return false;
    }

    private static boolean constantTimeEquals(String expected, String actual) {
        byte[] a = expected.getBytes(StandardCharsets.UTF_8);
        byte[] b = actual.getBytes(StandardCharsets.UTF_8);
        if (a.length != b.length) {
            return false;
        }
        int diff = 0;
        for (int i = 0; i < a.length; i++) {
            diff |= a[i] ^ b[i];
        }
        return diff == 0;
    }
}
