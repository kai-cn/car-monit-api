package com.ruoyi.base.service.v3.export;

import lombok.Data;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 导出请求（展示字段 / 全字段共用）。
 */
@Data
public class ExportRequest {

    /** snapshot / fee / trail */
    private String table;

    private String startTime;
    private String endTime;

    /** 车牌（可含颜色后缀） */
    private String plate;
    private String colorCode;

    /** 维度编码过滤（orgcode/sectioncode/roadcode/gantrycode/tollcode） */
    private Map<String, java.util.List<String>> dimensionCodes = new LinkedHashMap<>();

    /** 展示字段（display 路径）：backend 传 camelCase 逻辑字段名 */
    private java.util.List<String> fields;

    /** 申请人（审计用；权限模型接入前仅记录） */
    private String requestedBy;

    /** 全字段导出用途说明（backend 已校验，api 侧仅记录/审计） */
    private String purpose;
}
