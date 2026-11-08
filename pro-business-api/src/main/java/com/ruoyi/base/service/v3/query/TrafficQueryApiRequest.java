package com.ruoyi.base.service.v3.query;

import lombok.Data;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * V3 对外查询请求体（支持 PIT + search_after 深分页）。
 */
@Data
public class TrafficQueryApiRequest {

    /** snapshot / fee / trail */
    private String table;

    private String startTime;
    private String endTime;

    /** 维度编码（名称需先在码表解析） */
    private Map<String, List<String>> dimensionCodes = new LinkedHashMap<>();

    private String plate;
    private String colorCode;

    private int pageSize = 20;
    private int pageNum = 1;

    /** 深分页游标；与 pitId 一起使用 */
    private List<Object> searchAfter = new ArrayList<>();
    private String pitId;

    private boolean needTotal = true;
}
