package com.ruoyi.base.agent.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

/**
 * 对话请求。
 */
@Data
public class AgentChatRequest {

    /** 会话 ID；为空时服务端新建并返回。 */
    @Size(max = 64)
    private String sessionId;

    @NotBlank
    @Size(max = 4000)
    private String message;

    /** 高风险操作的一次性确认令牌（由 /agent/confirm 签发），不会传给模型。 */
    @Size(max = 64)
    private String confirmToken;

    /** 语言标识，预留；当前固定 zh-CN。 */
    @Size(max = 16)
    private String locale;
}
