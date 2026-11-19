package com.ruoyi.base.agent.api.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class AgentConfirmRequest {

    @NotBlank
    @Size(max = 64)
    private String sessionId;

    /** 当前仅支持 export。 */
    @NotBlank
    @Size(max = 32)
    private String action;
}
