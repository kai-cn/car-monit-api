# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsSzdnProvinceBorderVehicleWeightNewstructure.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsSzdnProvinceBorderVehicleWeightNewstructure(JavaBean, Custom):
    """省界称重对象 ods_szdn_province_border_vehicle_weight_newstructure

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_szdn_province_border_vehicle_weight_newstructure") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_szdn_province_border_vehicle_weight_newstructure"  # @TableName("ods_szdn_province_border_vehicle_weight_newstructure")

    # @Excel(name = "数据来源")
    data_source: Optional[str] = None  # Java: private String dataSource; // 数据来源

    # @Excel(name = "数据类型")
    data_type: Optional[str] = None  # Java: private String dataType; // 数据类型

    # @Excel(name = "车牌号")
    plate_no: Optional[str] = None  # Java: private String plateNo; // 车牌号

    # @Excel(name = "站点ID")
    site_id: Optional[str] = None  # Java: private String siteId; // 站点ID

    # @Excel(name = "设备地点")
    location: Optional[str] = None  # Java: private String location; // 设备地点

    # @Excel(name = "车道号")
    drive_no: Optional[int] = None  # Java: private Long driveNo; // 车道号

    # @Excel(name = "车牌颜色索引")
    plate_color: Optional[str] = None  # Java: private String plateColor; // 车牌颜色索引

    # @Excel(name = "车牌颜色代码")
    plate_color_code: Optional[str] = None  # Java: private String plateColorCode; // 车牌颜色代码

    # @Excel(name = "车牌类型索引")
    plate_type: Optional[str] = None  # Java: private String plateType; // 车牌类型索引

    # @Excel(name = "车牌类型代码")
    plate_type_code: Optional[str] = None  # Java: private String plateTypeCode; // 车牌类型代码

    # @Excel(name = "车辆颜色代号")
    vehicle_color: Optional[str] = None  # Java: private String vehicleColor; // 车辆颜色代号

    # @Excel(name = "车辆颜色代码")
    vehicle_color_code: Optional[str] = None  # Java: private String vehicleColorCode; // 车辆颜色代码

    # @Excel(name = "车辆类型代号")
    vehicle_type: Optional[str] = None  # Java: private String vehicleType; // 车辆类型代号

    # @Excel(name = "车辆类型代码")
    vehicle_type_code: Optional[str] = None  # Java: private String vehicleTypeCode; // 车辆类型代码

    # @Excel(name = "车辆速度", readConverterExp = "k=m/h")
    vehicle_speed: Optional[int] = None  # Java: private Long vehicleSpeed; // 车辆速度（km/h）

    # @Excel(name = "是否超载")
    is_overweight: Optional[int] = None  # Java: private Long isOverweight; // 是否超载

    # @Excel(name = "轴数")
    axle_num: Optional[int] = None  # Java: private Long axleNum; // 轴数

    # @Excel(name = "超重量", readConverterExp = "K=G")
    over_weight: Optional[int] = None  # Java: private Long overWeight; // 超重量（KG）

    # @Excel(name = "重量", readConverterExp = "K=G")
    vehicle_weight: Optional[int] = None  # Java: private Long vehicleWeight; // 重量（KG）

    # @Excel(name = "车辆限重", readConverterExp = "K=G")
    limit_weight: Optional[int] = None  # Java: private Long limitWeight; // 车辆限重（KG）

    # @Excel(name = "检测时间Unix格式")
    check_time_unix: Optional[int] = None  # Java: private Long checkTimeUnix; // 检测时间Unix格式

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "检测时间", width = 30, dateFormat = "yyyy-MM-dd")
    check_time: Optional[datetime] = None  # Java: private Date checkTime; // 检测时间

    # @Excel(name = "轴型")
    axle_model: Optional[int] = None  # Java: private Long axleModel; // 轴型

    # @Excel(name = "超载率")
    load_rate: Optional[int] = None  # Java: private Long loadRate; // 超载率

    # @Excel(name = "轴型详细数据")
    axle_array: Optional[str] = None  # Java: private String axleArray; // 轴型详细数据

    # @Excel(name = "图片数组")
    weighing_images_arry: Optional[str] = None  # Java: private String weighingImagesArry; // 图片数组

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "加载时间", width = 30, dateFormat = "yyyy-MM-dd")
    load_time: Optional[datetime] = None  # Java: private Date loadTime; // 加载时间

    # @Excel(name = "分类分级")
    grade_level: Optional[int] = None  # Java: private Long gradeLevel; // 分类分级

    # @TableId(value = "datauuid", type = IdType.ASSIGN_UUID) @Excel(name = "datauuid")
    datauuid: Optional[str] = field(default=None, metadata={"table_id": "datauuid", "id_type": "ASSIGN_UUID"})  # Java: private String datauuid; // datauuid

    reserve1: Optional[str] = None  # Java: private String reserve1;

    reserve2: Optional[str] = None  # Java: private String reserve2;

    reserve3: Optional[str] = None  # Java: private String reserve3;

    # @TableField(exist = false)
    query_uuids: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String queryUuids;

