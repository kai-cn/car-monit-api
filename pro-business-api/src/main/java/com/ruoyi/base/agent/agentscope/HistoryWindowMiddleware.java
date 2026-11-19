package com.ruoyi.base.agent.agentscope;

import io.agentscope.core.agent.Agent;
import io.agentscope.core.agent.RuntimeContext;
import io.agentscope.core.event.AgentEvent;
import io.agentscope.core.message.Msg;
import io.agentscope.core.message.MsgRole;
import io.agentscope.core.middleware.MiddlewareBase;
import io.agentscope.core.middleware.ReasoningInput;
import reactor.core.publisher.Flux;

import java.util.ArrayList;
import java.util.List;
import java.util.function.Function;

/**
 * 上下文窗口裁剪中间件：把回灌给模型的会话历史限制在最近 N 轮。
 *
 * <p>为什么需要它：{@code ReActAgent} 会把 {@code AgentState.context} 里的全部历史回放给模型，
 * 长会话下 token 成本线性增长，最终触发模型上下文超限（400/413）。框架本身没有窗口配置，
 * 这里用 {@code onReasoning} 钩子做“只裁回灌内容、不改持久化状态”的裁剪：</p>
 * <ul>
 *   <li>保留全部 system 消息（人设与安全约束不能被裁掉）；</li>
 *   <li>只保留最近 {@code historyWindow} 轮（一问一答为一轮）的对话；</li>
 *   <li>裁剪点向前对齐到 user 消息边界，避免把 {@code tool_use} 与其 {@code tool_result} 拆散，
 *       否则 OpenAI 兼容端点会直接拒绝请求（tool_call_id 不匹配）；</li>
 *   <li>找不到对齐边界时宁可不裁剪，保证请求合法优先于省 token。</li>
 * </ul>
 */
public class HistoryWindowMiddleware implements MiddlewareBase {

    private final int historyWindow;

    public HistoryWindowMiddleware(int historyWindow) {
        this.historyWindow = historyWindow;
    }

    @Override
    public Flux<AgentEvent> onReasoning(Agent agent,
                                        RuntimeContext ctx,
                                        ReasoningInput input,
                                        Function<ReasoningInput, Flux<AgentEvent>> next) {
        List<Msg> messages = input.messages();
        List<Msg> trimmed = trim(messages);
        if (trimmed.size() == messages.size()) {
            return next.apply(input);
        }
        return next.apply(new ReasoningInput(trimmed, input.tools(), input.options()));
    }

    /**
     * 裁剪规则见类注释。返回入参本身表示“未裁剪”。
     */
    List<Msg> trim(List<Msg> messages) {
        if (historyWindow <= 0 || messages == null || messages.isEmpty()) {
            return messages;
        }
        int keep = historyWindow * 2;
        int systemEnd = 0;
        while (systemEnd < messages.size() && messages.get(systemEnd).getRole() == MsgRole.SYSTEM) {
            systemEnd++;
        }
        List<Msg> body = messages.subList(systemEnd, messages.size());
        if (body.size() <= keep) {
            return messages;
        }
        int start = body.size() - keep;
        while (start < body.size() && body.get(start).getRole() != MsgRole.USER) {
            start++;
        }
        if (start >= body.size()) {
            return messages;
        }
        List<Msg> result = new ArrayList<>(systemEnd + body.size() - start);
        result.addAll(messages.subList(0, systemEnd));
        result.addAll(body.subList(start, body.size()));
        return result;
    }
}
