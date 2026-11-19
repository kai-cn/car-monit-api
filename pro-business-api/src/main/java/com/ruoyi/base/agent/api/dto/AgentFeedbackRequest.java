package com.ruoyi.base.agent.api.dto;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class AgentFeedbackRequest {

    @NotBlank
    @Size(max = 64)
    private String requestId;

    @Size(max = 64)
    private String sessionId;

    /** 1=有帮助，-1=没帮助。 */
    @Min(-1)
    @Max(1)
    private int rating;

    @Size(max = 500)
    private String comment;
}
