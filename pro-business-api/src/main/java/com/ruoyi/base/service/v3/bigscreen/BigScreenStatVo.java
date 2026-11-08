package com.ruoyi.base.service.v3.bigscreen;

import lombok.Data;

import java.math.BigDecimal;

/**
 * 大屏预聚合查询返回 DTO（字段名与 backend 侧 VO 严格一致）。
 */
public final class BigScreenStatVo {

    private BigScreenStatVo() {
    }

    /** 对应 backend CarStatisticsVO */
    @Data
    public static class Escape {
        private String escapedType;
        private String escapedTypeName;
        private Integer number = 0;
        private BigDecimal escapedAmount = BigDecimal.ZERO;
    }

    /** 对应 backend CarAuditVO */
    @Data
    public static class Audit {
        private Integer totalCount = 0;
        private Integer finishedCount = 0;
        private BigDecimal totalAmount = BigDecimal.ZERO;
        private BigDecimal finishedAmount = BigDecimal.ZERO;
    }

    /** 对应 backend incomeStatisticVO */
    @Data
    public static class Income {
        private String orgName;
        private BigDecimal amount;
        private Integer carNum;
    }

    /** 对应 backend TopTenVO */
    @Data
    public static class WarningTop {
        private String roadCode;
        private String sectionName;
        private Integer carNum;
        private Integer rank;
        private String rate;
    }
}
