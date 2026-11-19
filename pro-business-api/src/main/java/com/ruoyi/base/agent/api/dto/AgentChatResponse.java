package com.ruoyi.base.agent.api.dto;

import lombok.Data;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 同步对话响应（供 backend/BFF 聚合调用）。
 */
@Data
public class AgentChatResponse {

    private String requestId;
    private String sessionId;
    private String answer;
    private List<Map<String, Object>> toolCalls = new ArrayList<>();
    private Map<String, Object> usage = new LinkedHashMap<>();
    private long elapsedMs;
    private String finishReason;
}
