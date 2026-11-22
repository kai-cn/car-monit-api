package com.ruoyi.base.service.v3.model;

import java.time.YearMonth;
import java.time.format.DateTimeFormatter;

/**
 * V3 三张核心表的统一元数据。
 *
 * <p>索引命名遵循设计 §5.3.1：按月一个索引，读别名 {@code *-read}，写别名 {@code *-write}。
 * 字段名与 ES mapping 保持一致，避免在查询/同步/导出之间出现口径漂移。</p>
 */
public enum TrafficTable {

    SNAPSHOT("snapshot", "snapshot-flow", "snapshottime", "big_id",
            "jl_data01.ods_rt_szdn_snapshot_flow_addcode"),

    FEE("fee", "fee-records", "transtime", "big_id",
            "jl_data01.ods_lwzxsfsj_fee_records_01"),

    TRAIL("trail", "trail-fitting", "extime", "cid",
            "jl_data01.zdata_trail_fitting");

    private static final DateTimeFormatter YM = DateTimeFormatter.ofPattern("yyyyMM");

    private final String paramName;
    private final String indexBase;
    private final String timeField;
    private final String pkField;
    private final String sourceTable;

    TrafficTable(String paramName, String indexBase, String timeField, String pkField, String sourceTable) {
        this.paramName = paramName;
        this.indexBase = indexBase;
        this.timeField = timeField;
        this.pkField = pkField;
        this.sourceTable = sourceTable;
    }

    public String getParamName() {
        return paramName;
    }

    public String getIndexBase() {
        return indexBase;
    }

    public String getTimeField() {
        return timeField;
    }

    public String getPkField() {
        return pkField;
    }

    public String getSourceTable() {
        return sourceTable;
    }

    /** 具体月索引名，如 snapshot-flow-202611 */
    public String monthlyIndex(YearMonth yearMonth) {
        return indexBase + "-" + YM.format(yearMonth);
    }

    /** 读别名（指向保留期内所有月索引） */
    public String readAlias() {
        return indexBase + "-read";
    }

    /** 写别名（当月写入） */
    public String writeAlias() {
        return indexBase + "-write";
    }

    /** ES 车牌统一字段名（由 plate_core/platenumber/envehicleid 归一） */
    public String plateNormField() {
        return "plate_norm";
    }

    public static TrafficTable fromParam(String value) {
        if (value == null) {
            return SNAPSHOT;
        }
        String v = value.trim().toLowerCase();
        for (TrafficTable t : values()) {
            if (t.paramName.equals(v) || t.name().toLowerCase().equals(v) || t.indexBase.equals(v)) {
                return t;
            }
        }
        throw new IllegalArgumentException("未知表类型: " + value + "（可选 snapshot/fee/trail）");
    }

    /**
     * 兼容 Outbox 中写的物理表名（含 schema 前缀）。
     */
    public static TrafficTable fromSourceTableOrParam(String value) {
        if (value == null) {
            return SNAPSHOT;
        }
        String v = value.trim().toLowerCase();
        for (TrafficTable t : values()) {
            String source = t.sourceTable.toLowerCase();
            if (v.equals(source) || v.endsWith("." + t.getSourceTableOnly())
                    || v.equals(t.getSourceTableOnly())) {
                return t;
            }
        }
        return fromParam(value);
    }

    private String getSourceTableOnly() {
        int dot = sourceTable.lastIndexOf('.');
        return dot >= 0 ? sourceTable.substring(dot + 1) : sourceTable;
    }

}
