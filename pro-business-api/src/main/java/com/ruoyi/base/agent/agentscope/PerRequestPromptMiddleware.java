package com.ruoyi.base.agent.agentscope;

import com.ruoyi.base.agent.core.AgentPrincipal;
import com.ruoyi.base.agent.core.PromptLibrary;
import com.ruoyi.base.agent.core.ToolContextKeys;
import io.agentscope.core.agent.Agent;
import io.agentscope.core.agent.RuntimeContext;
import io.agentscope.core.middleware.MiddlewareBase;
import reactor.core.publisher.Mono;

/**
 * 逐请求渲染系统提示词。
 *
 * <p>{@code ReActAgent} 的 {@code sysPrompt} 在 build 期固定，而提示词里的
 * {@code {{tenantId}}/{{userId}}/{{roles}}/{{now}}} 是“每次请求都不同且必须由服务端注入”的值
 * （模型无法伪造）。这里用 {@code onSystemPrompt} 钩子按调用主体重新渲染：</p>
 * <ul>
 *   <li>保证租户/角色上下文与当前请求严格一致，避免复用进程内固定提示词造成串号；</li>
 *   <li>提示词模板仍然只有一份（classpath 资源），便于评审与灰度；</li>
 *   <li>拿不到调用主体时保持原提示词（builder 里设置的是模板原文），不放大失败面。</li>
 * </ul>
 */
public class PerRequestPromptMiddleware implements MiddlewareBase {

    private final PromptLibrary promptLibrary;

    public PerRequestPromptMiddleware(PromptLibrary promptLibrary) {
        this.promptLibrary = promptLibrary;
    }

    @Override
    public Mono<String> onSystemPrompt(Agent agent, RuntimeContext ctx, String currentPrompt) {
        if (ctx == null) {
            return Mono.just(currentPrompt);
        }
        Object principal = ctx.get(ToolContextKeys.PRINCIPAL);
        if (!(principal instanceof AgentPrincipal p)) {
            return Mono.just(currentPrompt);
        }
        String rendered = promptLibrary.render(p);
        return Mono.just(rendered == null || rendered.isBlank() ? currentPrompt : rendered);
    }
}
