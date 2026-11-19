package com.ruoyi.base.agent.core;

/**
 * 工具执行上下文的键名。两个框架适配层使用同一组键，
 * 工具实现只依赖这些键，不感知具体框架。
 */
public final class ToolContextKeys {

    public static final String PRINCIPAL = "agentPrincipal";
    public static final String INVOCATION = "agentInvocation";
    public static final String SINK = "agentEventSink";
    public static final String BUDGET = "agentToolBudget";
    public static final String CONFIRM_TOKEN = "agentConfirmToken";

    private ToolContextKeys() {
    }
}
