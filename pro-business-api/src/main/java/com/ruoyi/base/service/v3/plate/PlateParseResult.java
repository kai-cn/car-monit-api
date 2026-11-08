package com.ruoyi.base.service.v3.plate;

import lombok.Data;

/**
 * 车牌解析结果。
 *
 * <p>对应设计 §5.1.6：{@code 赣B21E85_0} -> plate_core=赣B21E85、plate_color_code=0、
 * plate_raw=赣B21E85_0；颜色码 {@code 0} 是合法值，未知/缺失为 {@code -1}。</p>
 */
@Data
public class PlateParseResult {

    /** 车牌核心（不含颜色后缀） */
    private String plateCore;

    /** 颜色枚举码；-1 表示未知/缺失 */
    private int plateColorCode = -1;

    /** 颜色展示名（来自 dict_plate_color；未知为“未知/未知(原码)”） */
    private String plateColorName;

    /** 原始颜色码/颜色文本 */
    private String plateColorRaw;

    /** 原始车牌（审计/兜底） */
    private String plateRaw;

    /** ok / no_color / color_unparsed / unparsed */
    private String plateParseStatus;

    public boolean isColorKnown() {
        return plateColorCode >= 0;
    }

    public static PlateParseResult unparsed(String raw, String core, String colorRaw) {
        PlateParseResult r = new PlateParseResult();
        r.plateRaw = raw;
        r.plateCore = core;
        r.plateColorRaw = colorRaw;
        r.plateColorCode = -1;
        r.plateParseStatus = PlateNumberParser.STATUS_UNPARSED;
        r.plateColorName = colorRaw == null || colorRaw.trim().isEmpty()
                ? "未知" : "未知(" + colorRaw.trim() + ")";
        return r;
    }
}
