package com.ruoyi.base.service.v3.sync;

import lombok.Data;

import java.util.Map;

/**
 * GaussDB -> ES 同步事件（Outbox payload / Kafka search-sync 消息体）。
 *
 * <p>{@code _id} 规则：抓拍/收费 = big_id，轨迹 = cid（设计 §4.2.4）。
 * 事件至少一次投递，靠幂等 _id 收敛重复。</p>
 */
@Data
public class SearchSyncEvent {

    /** 事件唯一 ID（Outbox 唯一键，用于去重） */
    private String eventId;

    /** 逻辑表名：snapshot / fee / trail（也兼容物理表名） */
    private String table;

    /** 主键值（big_id / cid） */
    private String pk;

    /** I=插入/更新，D=删除 */
    private String op = "I";

    /** 业务时间（epoch millis），用于定位月索引 */
    private Long eventTime;

    /** ES 展示字段；为空时消费者按 pk + 时间回查 GaussDB */
    private Map<String, Object> payload;

    /** 解析器/文档 schema 版本 */
    private int schemaVersion = 1;
}
