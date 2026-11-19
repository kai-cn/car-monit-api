package com.ruoyi.base.agent.core;

import com.ruoyi.base.agent.config.AgentProperties;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.regex.Pattern;

/**
 * 入参校验 + 提示词注入启发式检测。
 *
 * <p>检测不是安全边界（真正的边界是工具白名单与服务端租户过滤），
 * 目的是在入口拦掉明显的越权/套取提示词尝试并留下审计信号。</p>
 */
@Slf4j
@Component
public class AgentGuard {

    private static final List<Pattern> INJECTION_PATTERNS = List.of(
            Pattern.compile("(?i)ignore\\s+(all\\s+)?(previous|above|prior)\\s+instructions?"),
            Pattern.compile("(?i)(reveal|show|print|repeat)\\s+(me\\s+)?(your\\s+)?(system\\s+)?prompt"),
            Pattern.compile("(?i)(developer|god|dan)\\s+mode|jailbreak|开发者模式|调试模式"),
            Pattern.compile("忽略(以上|之前|前面|上面).{0,8}(指令|提示|要求)"),
            Pattern.compile("(输出|打印|告诉我|复述).{0,8}(系统提示词|系统指令|你的提示词|prompt)"),
            Pattern.compile("(你现在是|从现在开始你是|扮演).{0,12}(管理员|开发者|root|超级用户)"),
            Pattern.compile("(泄露|导出|给我|告诉我|提供).{0,8}(密钥|token|密码|口令|api[_-]?key)"),
            Pattern.compile("(base64|十六进制|倒序).{0,10}(输出|编码).{0,10}(提示词|指令)")
    );

    private final AgentProperties properties;

    public AgentGuard(AgentProperties properties) {
        this.properties = properties;
    }

    public void validateMessage(String message) {
        if (message == null || message.isBlank()) {
            throw AgentException.badRequest("message 不能为空");
        }
        if (message.length() > properties.getMaxMessageChars()) {
            throw AgentException.badRequest("message 超过 " + properties.getMaxMessageChars() + " 字符");
        }
        for (Pattern p : INJECTION_PATTERNS) {
            if (p.matcher(message).find()) {
                throw new AgentException(AgentErrorCode.AGENT_PROMPT_REJECTED,
                        "问题包含可能绕过系统约束的指令，请改为直接描述要查询的数据");
            }
        }
    }

    public void requireRole(AgentPrincipal principal, String... roles) {
        if (!principal.hasAnyRole(roles)) {
            throw AgentException.forbidden("当前角色无权执行该操作");
        }
    }

    public void requireExportEnabled() {
        if (!properties.isAllowExport()) {
            throw AgentException.forbidden("导出能力未开启");
        }
    }
}
