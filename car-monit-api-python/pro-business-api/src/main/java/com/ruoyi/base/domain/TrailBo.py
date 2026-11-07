# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.TrailBo

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/TrailBo.java
"""
from __future__ import annotations

from decimal import Decimal

from dataclasses import dataclass
from typing import Any, Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean


@dataclass
class TrailBo(JavaBean):
    """TrailBo

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) 无 @TableName（非表实体 / VO / DTO）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) 原 Java 里有 9 个**没有访问修饰符**（包级私有）的 BO 引用字段
       （borderWeighingCaptureBO / gantryCaptureBO / ... / stationIpBO）。
       Lombok @Data 对它们同样生成 getter/setter，所以必须保留；
       类型用 Any 避免 domain 之间循环 import（运行期不校验具体类型，与 Java 泛型擦除同理）。
    """
    point_uuid: Optional[str] = None  # Java: private String pointUuid; // 流水唯一标识符:用于标识单条抓拍或收费流水的唯一性，支持去重、追踪和跨表关联

    state_type: Optional[str] = None  # Java: private String stateType; // 流水来源类型标识:可作为维度字段，用于回溯数据来源、确定查找目标表： 省界称重：BorderWeighingCapture 门架抓拍 GantryCapture 省界抓拍 ProvCapture 服务区抓拍 ServiceAreaCapture 收费站抓拍 StationCapture

    # 以下 7 个字段在 Java 里没有 private 修饰符（包级私有），Lombok 仍生成 getter/setter
    border_weighing_capture_bo: Optional[Any] = None  # Java: OdsSzdnProvinceBorderVehicleWeightNewstructure borderWeighingCaptureBO; // 省界称重

    gantry_capture_bo: Optional[Any] = None  # Java: OdsRtSzdnSnapshotFlowAddcode gantryCaptureBO; // 门架抓拍

    prov_capture_bo: Optional[Any] = None  # Java: OdsRtSzdnSnapshotFlowProvcaptureAddcode provCaptureBO; // 省界抓拍

    station_capture: Optional[Any] = None  # Java: OdsRtSzdnSnapshotFlowStationcaptureAddcode stationCapture; // 收费站抓拍

    fee_record: Optional[Any] = None  # Java: OdsLwzxsfsjFeeRecords01 feeRecord; // 卡口流水

    fee_station_enter: Optional[Any] = None  # Java: OdsLwzxsfsjFeeStationEnter01 feeStationEnter; // 收费站入口流水

    fee_station_exit: Optional[Any] = None  # Java: OdsLwzxsfsjFeeStationExit01 feeStationExit; // 收费站出口流水

    point_flag: Optional[str] = None  # Java: private String pointFlag; // 是否有值 O否 1是

    point_josn: Optional[str] = None  # Java: private String pointJosn; // pointUuid josn对象

    capture_time: Optional[str] = None  # Java: private String captureTime; // 抓拍流水发生时间:用于轨迹拼接、排序和时序分析

    direction_in: Optional[bool] = None  # Java: private Boolean directionIn; // 车辆在收费站的进出方向:用于区分车流方向，支撑进出站逻辑和轨迹起止点判定 true=进入，false=驶出，null=非进出类

    location_code: Optional[str] = None  # Java: private String locationCode; // 设备IP地址:可通过映射表解析IP→实体设施（门架、收费站、服务区等），实现设备到道路设施的转换

    location_name: Optional[str] = None  # Java: private String locationName; // 设备名称

    standard_code: Optional[str] = None  # Java: private String standardCode; // 标准代码

    longitude: Optional[str] = None  # Java: private String longitude; // 进度

    latitude: Optional[str] = None  # Java: private String latitude; // 维度

    location_flag: Optional[str] = None  # Java: private String locationFlag; // 位置是否有值

    ip_type: Optional[str] = None  # Java: private String ipType; // ip类型 : gantryip 门架ip stationip 收费站ip

    location_josn: Optional[str] = None  # Java: private String locationJosn; // 位置josn 对象

    # 同样是包级私有字段（无 private 修饰符）
    gantry_ip_bo: Optional[Any] = None  # Java: OdsSzdnGantryIp gantryIpBO; // 门架IP

    station_ip_bo: Optional[Any] = None  # Java: OdsSzdnTollStationIp stationIpBO; // 收费站ip

    dev_code: Optional[str] = None  # Java: private String devCode; // 设备编码

    dev_name: Optional[str] = None  # Java: private String devName; // 设备名称

    images_arry: Optional[str] = None  # Java: private String imagesArry; // 抓拍图片

    lon: Optional[Decimal] = None  # Java: private BigDecimal lon; // 经度

    lat: Optional[Decimal] = None  # Java: private BigDecimal lat; // 维度

    road_code: Optional[str] = None  # Java: private String roadCode; // 路线编号

    section_code: Optional[str] = None  # Java: private String sectionCode; // 路段编号

    org_code: Optional[str] = None  # Java: private String orgCode; // 机构编码

    direction: Optional[str] = None  # Java: private String direction; // 方向（0: 上行，1: 下行）

    pileno: Optional[str] = None  # Java: private String pileno; // 桩号

    pre_capture_time: Optional[str] = None  # Java: private String preCaptureTime; // 上一个抓拍时间

    count_num: Optional[int] = None  # Java: private Integer countNum; // 数量

    platenumber: Optional[str] = None  # Java: private String platenumber;

    location_id: Optional[str] = None  # Java: private String locationId;

    is_query: Optional[str] = None  # Java: private String isQuery; // 是否查询：1查询

    platecolor: Optional[str] = None  # Java: private String platecolor; // 车牌颜色

    is_virtual: Optional[str] = None  # Java: private String isVirtual; // '是否虚门架 0=：否，1：是

