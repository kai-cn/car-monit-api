package com.ruoyi.base.domain;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.ruoyi.common.annotation.Excel;
import lombok.Data;

import java.util.Date;
import java.util.List;

@Data
public class TrailInfo {

    //  轨迹ID
    private String trailUuid;

    /**
     * 进入时间（分区键，月度分区粒度）
     */
    private Date enterTime;

    // 轨迹对象
    private ZdataTrailTracks tracks;

    /**
     * 轨迹详情
     */
    private List<TrailBo> trailList;


    /**
     * 路线轨迹
     */
    // private List<Geometry> raodTrailList;

}
