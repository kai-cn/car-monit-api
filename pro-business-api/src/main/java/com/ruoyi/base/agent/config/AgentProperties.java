package com.ruoyi.base.agent.config;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

import java.time.Duration;

/**
 * 路网数据智能助手配置。
 *
 * <p>前缀 {@code traffic.agent}。默认关闭，避免在没有模型凭据的环境里影响
 * 现有接口与启动流程；开启后所有必填项在 {@code AgentConfiguration} 中校验。</p>
 */
@Data
@Component
@ConfigurationProperties(prefix = "traffic.agent")
public class AgentProperties {

    /** 总开关：false 时不注册任何 Agent Bean/端点。 */
    private boolean enabled = false;

    /** 实现框架标识，仅用于健康检查/审计展示：spring-ai / agentscope。 */
    private String framework = "spring-ai";

    /** OpenAI 兼容端点，例如 https://dashscope.aliyuncs.com/compatible-mode/v1 。 */
    private String baseUrl = "";

    /** 模型 API Key，必须通过环境变量注入，禁止写入仓库。 */
    private String apiKey = "";

    /** 对话模型名称，例如 qwen-plus / deepseek-chat / gpt-4.1-mini 。 */
    private String model = "qwen-plus";

    /** 采样温度：数据问答场景默认低温度，降低幻觉。 */
    private double temperature = 0.2;

    /** 单次回复最大 token。 */
    private int maxOutputTokens = 1024;

    /**
     * 单次请求最多工具轮数（ReAct 迭代上限）。
     * 超过后返回 {@code AGENT_MAX_ITERS}，避免模型陷入工具循环。
     */
    private int maxIters = 6;

    /** 模型调用超时（连接 + 首包 + 完整响应）。 */
    private Duration modelTimeout = Duration.ofSeconds(60);

    /** 整个 HTTP/SSE 请求的超时。 */
    private Duration requestTimeout = Duration.ofSeconds(120);

    /** 单个工具执行超时。 */
    private Duration toolTimeout = Duration.ofSeconds(20);

    /** 会话记忆保留轮数（一问一答算 1 轮），同时作为上下文窗口上限。 */
    private int historyWindow = 10;

    /** 单条用户消息最大字符数。 */
    private int maxMessageChars = 4000;

    /** 单个工具结果回灌给模型前的最大字符数。 */
    private int maxToolResultChars = 8000;

    /** 单用户每分钟请求上限。 */
    private int rateLimitPerUserPerMinute = 10;

    /** 单租户每分钟请求上限。 */
    private int rateLimitPerTenantPerMinute = 120;

    /** 同时进行中的 Agent 请求上限（保护模型配额与线程池）。 */
    private int maxConcurrentRequests = 32;

    /** 是否允许导出类工具（高风险，默认关闭）。 */
    private boolean allowExport = false;

    /** 是否把模型思考过程（thinking）透传给前端；生产默认关闭。 */
    private boolean exposeThinking = false;

    /** 审计日志是否记录原始问题文本（含车牌等敏感信息，默认关闭）。 */
    private boolean auditLogQuestion = false;

    /** 知识库 Markdown 位置（classpath 通配）。 */
    private String knowledgeLocation = "classpath*:agent/knowledge/*.md";

    /** 系统提示词位置。 */
    private String promptLocation = "classpath:agent/prompts/system.md";

    /** 租户请求头（由网关/backend 注入，Agent 只读不信任模型）。 */
    private String tenantHeader = "X-Tenant-Id";

    /** 用户请求头。 */
    private String userHeader = "X-User-Id";

    /** 角色请求头，逗号分隔，例如 ops,audit,admin 。 */
    private String rolesHeader = "X-User-Roles";

    /** 请求追踪号请求头；缺省时服务端生成。 */
    private String requestIdHeader = "X-Request-Id";

    /** 本机回环调用是否允许跳过内部令牌（仅单机联调，生产必须为 false）。 */
    private boolean allowLoopbackWithoutToken = true;

    /** SSE 心跳间隔。 */
    private Duration heartbeatInterval = Duration.ofSeconds(15);

    /** 会话 TTL。 */
    private Duration sessionTtl = Duration.ofDays(7);

    /** 确认令牌 TTL（导出等高风险操作）。 */
    private Duration confirmTtl = Duration.ofMinutes(5);

    /** 对话记忆 Redis key 前缀。 */
    private String keyPrefix = "agent";
}
