package com.ruoyi.base.service.v3.sync;

import com.ruoyi.base.service.v3.model.TrafficTable;
import lombok.Data;

import java.util.Date;

/**
 * 回灌任务模型（用于运维接口/脚本轮询）。
 */
@Data
public class BackfillTask {

    private String taskId;
    private TrafficTable table;
    private long startMillis;
    private long endMillis;
    /** RUNNING / DONE / FAILED / CANCELED */
    private String status = "RUNNING";
    private long rowsIndexed;
    private Date lastEventTime;
    private String error;
    private Date createdAt = new Date();
    private Date finishedAt;
}
