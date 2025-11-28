package com.ruoyi.base.domain;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.annotation.Excel;
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
    @Excel(name = "车牌唯一标识", readConverterExp = "可=脱敏/加密存储，用于车辆关联")
    private String plateKey;

    /**
     * 进入时间（分区键，月度分区粒度）
     */
    @Excel(name = "进入时间", readConverterExp = "分=区键，月度分区粒度")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date enterTime;

    /**
     * 离开时间（轨迹结束时间）
     */
    @Excel(name = "离开时间", readConverterExp = "轨=迹结束时间")
    @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    private Date exitTime;

}
