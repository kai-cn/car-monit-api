package com.ruoyi.base.service.v3.query;

import com.ruoyi.base.service.v3.model.TrafficTable;
import lombok.Data;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * V3 组合查询请求：时间范围 + 维度编码 term + 车牌模糊。
 */
@Data
public class TrafficSearchRequest {

    private TrafficTable table;

    /** 开始时间（epoch millis，必填，默认最近 7 天） */
    private Long startMillis;

    /** 结束时间（epoch millis，必填，默认 now） */
    private Long endMillis;

    /**
     * 维度编码过滤：orgcode/sectioncode/roadcode/gantrycode/tollcode，
     * 值必须已由码表解析为编码（名称模糊不走事实表 ngram）。
     */
    private Map<String, List<String>> dimensionCodes = new LinkedHashMap<>();

    /** 车牌输入（可含颜色后缀，如 赣B21E85_0） */
    private String plate;

    /** 颜色码过滤（收费表），可选；未选时不加该子句 */
    private String colorCode;

    /** 单页大小，默认 20，上限 100 */
    private int pageSize = 20;

    /** 页码（1-based），深分页时才使用 searchAfter */
    private int pageNum = 1;

    /** search_after 游标（与 pitId 配合使用） */
    private List<Object> searchAfter = new ArrayList<>();

    /** PIT id；为空时服务端开启后关闭（普通分页） */
    private String pitId;

    /** 是否需要总数（默认封顶计数） */
    private boolean needTotal = true;

    /** 是否保留 PIT 供下一页使用（V3 接口传 true） */
    private boolean keepPit = false;

    public void addCodes(String field, List<String> codes) {
        if (field == null || codes == null || codes.isEmpty()) {
            return;
        }
        dimensionCodes.put(field, codes);
    }
}
