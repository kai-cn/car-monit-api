package com.ruoyi.base.task;

import com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowAddcode;
import com.ruoyi.base.service.IOdsRtSzdnSnapshotFlowAddcodeService;
import com.ruoyi.base.service.impl.MultiSourceDataFlowService;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.Date;
import java.util.List;

/**
 * 多源数据流转定时任务
 *
 * 功能说明：
 * 1. 定时处理待处理队列
 * 2. 示例：定时从数据库读取新数据并流转
 */
@Slf4j
@Component
public class DataFlowTask {

    @Autowired
    private MultiSourceDataFlowService dataFlowService;

    @Autowired
    private IOdsRtSzdnSnapshotFlowAddcodeService snapshotFlowService;

    /**
     * 处理待处理队列
     *
     * 思路：每60秒执行一次，处理队列中的乱序数据
     * 目的：保障轨迹完整性
     */
    @Scheduled(cron = "0 */1 * * * ?")
    public void processPendingQueue() {
        log.info("[定时任务] 开始处理待处理队列：{}", new Date());
        try {
            dataFlowService.processPendingQueue();
        } catch (Exception e) {
            log.error("[定时任务] 待处理队列处理异常", e);
        }
    }

    /**
     * 示例：定时同步门架抓拍数据
     *
     * 思路：每分钟读取最近5分钟的新数据，推送到数据流转服务
     * 目的：演示如何将数据库数据接入流转系统
     *
     * 注意：实际项目中建议使用Kafka CDC方式实时捕获变更
     */
    @Scheduled(cron = "0 */5 * * * ?")
    public void syncGantryCaptureData() {
        log.info("[定时任务] 开始同步门架抓拍数据：{}", new Date());
        try {
            // 查询最近5分钟的新数据
            // 这里需要根据实际业务实现查询逻辑
            // List<OdsRtSzdnSnapshotFlowAddcode> newData = ...;

            // 逐条处理数据
            // for (OdsRtSzdnSnapshotFlowAddcode data : newData) {
            //     dataFlowService.processData(data, "GantryCapture");
            // }

        } catch (Exception e) {
            log.error("[定时任务] 门架抓拍数据同步异常", e);
        }
    }
}
