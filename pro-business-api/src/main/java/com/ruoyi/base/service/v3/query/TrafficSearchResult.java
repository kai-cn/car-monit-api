package com.ruoyi.base.service.v3.query;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * V3 组合查询结果。
 */
@Data
public class TrafficSearchResult {

    /** ES _source 行（未转换为领域对象） */
    private List<Map<String, Object>> rows = new ArrayList<>();

    /** 总数（track_total_hits 封顶，不是精确值） */
    private long total;

    /** 是否可能还有下一页 */
    private boolean hasMore;

    /** PIT id（keepPit=true 时返回给客户端，用于下一页） */
    private String pitId;

    /** 下一页 search_after 游标 */
    private List<Object> searchAfter = new ArrayList<>();

    /** 查询耗时（毫秒） */
    private long tookMs;

    public boolean isEmpty() {
        return rows == null || rows.isEmpty();
    }
}
