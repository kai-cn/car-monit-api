package com.ruoyi.base.service.v3.export;

import com.ruoyi.base.service.v3.model.TrafficTable;
import lombok.Data;

import java.util.Date;

/**
 * 导出任务模型。
 *
 * <p>状态机：pending -> running -> done/failed/canceled。当前<b>不支持断点续传</b>：
 * 任务状态只存在内存，API 重启后任务丢失（已完成的文件仍可通过 taskId 探测下载），
 * 需要断点续传能力时再引入持久化任务表与 lastSort/lastPartition 字段。</p>
 */
@Data
public class ExportTask {

    private String taskId;
    private TrafficTable table;
    /** DISPLAY=ES PIT；FULL=GaussDB 分区游标 */
    private String mode;
    private String status = "pending";
    private long startMillis;
    private long endMillis;
    /** 预计总数（ES 封顶计数；全字段导出为 -1） */
    private long totalRows = -1;
    private long exportedRows;
    private String filePath;
    private String error;
    private String requestedBy;
    private String purpose;
    private boolean cancelRequested;
    private Date createdAt = new Date();
    private Date startedAt;
    private Date finishedAt;
}
