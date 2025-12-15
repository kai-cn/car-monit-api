package com.ruoyi.base.domain;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.core.domain.Custom;
import lombok.Data;

import java.util.Date;

/**
 * 轨迹数据对象 zdata_trail_tracks
 *
 * @author ruoyi
 * @date 2025-09-18
 */
@Data
public class TrailTracksVo implements Custom {

    /**
     * 车牌唯一标识（可脱敏/加密存储，用于车辆关联）
     */
    private String plateKey;

    /**
     * 进入时间（分区键，月度分区粒度）
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date enterTime;

    /**
     * 离开时间（轨迹结束时间）
     */
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date exitTime;

    /**
     * 轨迹点
     */
    private String trailpoints;

    /**
     * 车牌型号
     */
    private String envehicletype;

}
