# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.ZdataTrailTracks

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/ZdataTrailTracks.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class ZdataTrailTracks(JavaBean, Custom):
    """轨迹数据对象 zdata_trail_tracks

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("zdata_trail_tracks") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "zdata_trail_tracks"  # @TableName("zdata_trail_tracks")

    # @TableId(value = "uuid", type = IdType.ASSIGN_UUID) @Excel(name = "唯一标识符", readConverterExp = "分=布键，用于保证轨迹全局唯一")
    uuid: Optional[str] = field(default=None, metadata={"table_id": "uuid", "id_type": "ASSIGN_UUID"})  # Java: private String uuid; // 唯一标识符（分布键，用于保证轨迹全局唯一）

    # @Excel(name = "轨迹类型", readConverterExp = "如=,0==不完整,,1==完整，后续可扩展更多状态码")
    type: Optional[int] = None  # Java: private Integer type; // 轨迹类型（如 0=不完整, 1=完整，后续可扩展更多状态码）

    # @Excel(name = "轨迹点数量", readConverterExp = "记=录该轨迹包含多少个点")
    point_count: Optional[int] = None  # Java: private Long pointCount; // 轨迹点数量（记录该轨迹包含多少个点）

    # @Excel(name = "车牌唯一标识", readConverterExp = "可=脱敏/加密存储，用于车辆关联")
    plate_key: Optional[str] = None  # Java: private String plateKey; // 车牌唯一标识（可脱敏/加密存储，用于车辆关联）

    # @Excel(name = "进入时间", readConverterExp = "分=区键，月度分区粒度") @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    enter_time: Optional[datetime] = None  # Java: private Date enterTime; // 进入时间（分区键，月度分区粒度）

    # @Excel(name = "离开时间", readConverterExp = "轨=迹结束时间") @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss")
    exit_time: Optional[datetime] = None  # Java: private Date exitTime; // 离开时间（轨迹结束时间）

    # @Excel(name = "轨迹点集合，推荐存 JSON 格式，包含坐标/时间/速度等信息")
    trail_points: Optional[str] = None  # Java: private String trailPoints; // 轨迹点集合，推荐存 JSON 格式，包含坐标/时间/速度等信息

    # @Excel(name = "进入位置code")
    enter_locationcode: Optional[str] = None  # Java: private String enterLocationcode; // 进入位置code

    # @Excel(name = "离开位置code")
    exit_locationcode: Optional[str] = None  # Java: private String exitLocationcode; // 离开位置code

    # @Excel(name = "集合详情") @TableField(exist = false)
    track_josn: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String trackJosn; // 集合详情

    # @Excel(name = "入口车轴数") @TableField(exist = false)
    enaxlecount: Optional[int] = field(default=None, metadata={"exist": False})  # Java: private Integer enaxlecount; // 入口车轴数

    # @Excel(name = "入口车道编号") @TableField(exist = false)
    entolllaneid: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String entolllaneid; // 入口车道编号

    # @Excel(name = "入口收费站编号") @TableField(exist = false)
    entollstationid: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String entollstationid; // 入口收费站编号

    # @Excel(name = "入口收费站名称") @TableField(exist = false)
    entollstationname: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String entollstationname; // 入口收费站名称

    # @Excel(name = "入口车型分类", readConverterExp = "收=费车型") @TableField(exist = false)
    envehicleclass: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String envehicleclass; // 入口车型分类（收费车型）

    # @Excel(name = "入口车辆编号") @TableField(exist = false)
    envehicleid: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String envehicleid; // 入口车辆编号

    # @Excel(name = "入口车辆类型代码") @TableField(exist = false)
    envehicletype: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String envehicletype; // 入口车辆类型代码

    # @Excel(name = "入口称重", readConverterExp = "k=g") @TableField(exist = false)
    enweight: Optional[float] = field(default=None, metadata={"exist": False})  # Java: private BigDecimal enweight; // 入口称重（kg）

    # @Excel(name = "出口车道编号") @TableField(exist = false)
    extolllaneid: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String extolllaneid; // 出口车道编号

    # @Excel(name = "出口收费站编号") @TableField(exist = false)
    extollstationid: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String extollstationid; // 出口收费站编号

    # @Excel(name = "出口收费站名称") @TableField(exist = false)
    extollstationname: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String extollstationname; // 出口收费站名称

    # @Excel(name = "出口车型分类") @TableField(exist = false)
    exvehicleclass: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String exvehicleclass; // 出口车型分类

    # @Excel(name = "出口车辆编号") @TableField(exist = false)
    exvehicleid: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String exvehicleid; // 出口车辆编号

    # @Excel(name = "出口车辆类型代码") @TableField(exist = false)
    exvehicletype: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String exvehicletype; // 出口车辆类型代码

    # @Excel(name = "出口称重", readConverterExp = "k=g") @TableField(exist = false)
    exweight: Optional[float] = field(default=None, metadata={"exist": False})  # Java: private BigDecimal exweight; // 出口称重（kg）

    # @Excel(name = "入口收费站经度") @TableField(exist = false)
    start_lon: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String startLon; // 入口收费站经度

    # @Excel(name = "入口收费站维度") @TableField(exist = false)
    strat_lat: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String stratLat; // 入口收费站维度

    # @Excel(name = "出口收费站经度") @TableField(exist = false)
    end_lon: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String endLon; // 出口收费站经度

    # @Excel(name = "出口收费站维度") @TableField(exist = false)
    end_lat: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String endLat; // 出口收费站维度

    # @TableField(exist = false)
    firt_station_code: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String firtStationCode; // 入栈口

    # @TableField(exist = false)
    firt_station_name: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String firtStationName; // 入栈口名称

    # @TableField(exist = false)
    firt_station_time: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String firtStationTime; // 入栈口时间

    # @TableField(exist = false)
    plate_color: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String plateColor; // 车牌颜色（字典：1白色2黑色）

    # @TableField(exist = false)
    car_type: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String carType; // 车型

    # @TableField(exist = false)
    car_no: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String carNo; // 车牌号

    # @TableField(exist = false)
    car_vehicle: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String carVehicle; // 车种

    # @TableField(exist = false)
    car_num: Optional[int] = field(default=None, metadata={"exist": False})  # Java: private Long carNum; // 轴数

    # @TableField(exist = false)
    pass_type: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String passType; // 通行标识

    # @TableField(exist = false)
    escaped_type: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String escapedType; // 逃费类型

    # @TableField(exist = false)
    escaped_type_remark: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String escapedTypeRemark; // 逃费类型：原因

    # @TableField(exist = false)
    apply_time1: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String applyTime1; // 申请时间1

    # @TableField(exist = false)
    apply_time2: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String applyTime2; // 申请时间2

    # @TableField(exist = false)
    flag: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String flag; // 标识

    # @Excel(name = "入口收费站经度") @TableField(exist = false)
    start_lon_dec: Optional[float] = field(default=None, metadata={"exist": False})  # Java: private BigDecimal startLonDec; // 入口收费站经度

    # @Excel(name = "入口收费站维度") @TableField(exist = false)
    strat_lat_dec: Optional[float] = field(default=None, metadata={"exist": False})  # Java: private BigDecimal stratLatDec; // 入口收费站维度 /*

    # @Excel(name = "出口收费站经度") @TableField(exist = false)
    end_lon_dec: Optional[float] = field(default=None, metadata={"exist": False})  # Java: private BigDecimal endLonDec; // 出口收费站经度 /*

    # @Excel(name = "出口收费站维度") @TableField(exist = false)
    end_lat_dec: Optional[float] = field(default=None, metadata={"exist": False})  # Java: private BigDecimal endLatDec; // 出口收费站维度 /*

    # @TableField(exist = false)
    escaped_tfcj: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String escapedTfcj; // 逃费场景

    # @TableField(exist = false)
    trailtype: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String trailtype; // 业务类型 0 省外收费 1省内收费

