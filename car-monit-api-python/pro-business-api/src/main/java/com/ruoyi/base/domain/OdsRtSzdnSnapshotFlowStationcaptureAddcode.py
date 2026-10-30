# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowStationcaptureAddcode

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsRtSzdnSnapshotFlowStationcaptureAddcode.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsRtSzdnSnapshotFlowStationcaptureAddcode(JavaBean, Custom):
    """收费站抓拍对象 ods_rt_szdn_snapshot_flow_stationcapture_addcode

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_rt_szdn_snapshot_flow_stationcapture_addcode") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_rt_szdn_snapshot_flow_stationcapture_addcode"  # @TableName("ods_rt_szdn_snapshot_flow_stationcapture_addcode")

    # @TableId(value = "bigId", type = IdType.ASSIGN_UUID)
    big_id: Optional[int] = field(default=None, metadata={"table_id": "bigId", "id_type": "ASSIGN_UUID"})  # Java: private Long bigId;

    # @Excel(name = "数据类型")
    datasource: Optional[str] = None  # Java: private String datasource; // 数据类型

    # @Excel(name = "设备类型")
    cameratype: Optional[str] = None  # Java: private String cameratype; // 设备类型

    # @Excel(name = "设备编号")
    deviceid: Optional[str] = None  # Java: private String deviceid; // 设备编号

    # @Excel(name = "设备IP")
    deviceip: Optional[str] = None  # Java: private String deviceip; // 设备IP

    # @Excel(name = "收费站编码")
    tollcode: Optional[str] = None  # Java: private String tollcode; // 收费站编码

    # @Excel(name = "收费站名称")
    tollname: Optional[str] = None  # Java: private String tollname; // 收费站名称

    # @Excel(name = "组织机构编码")
    orgcode: Optional[int] = None  # Java: private Long orgcode; // 组织机构编码

    # @Excel(name = "站点ID")
    siteid: Optional[int] = None  # Java: private Long siteid; // 站点ID

    # @Excel(name = "车道编号")
    laneid: Optional[int] = None  # Java: private Integer laneid; // 车道编号

    # @Excel(name = "抓拍时间Unix格式")
    snapshottimeunix: Optional[int] = None  # Java: private Long snapshottimeunix; // 抓拍时间Unix格式

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "抓拍时间", width = 30, dateFormat = "yyyy-MM-dd")
    snapshottime: Optional[datetime] = None  # Java: private Date snapshottime; // 抓拍时间

    # @Excel(name = "接收时间Unix格式")
    receivedtimeunix: Optional[int] = None  # Java: private Long receivedtimeunix; // 接收时间Unix格式

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "接收时间", width = 30, dateFormat = "yyyy-MM-dd")
    receivedtime: Optional[datetime] = None  # Java: private Date receivedtime; // 接收时间

    # @Excel(name = "车牌号")
    platenumber: Optional[str] = None  # Java: private String platenumber; // 车牌号

    # @Excel(name = "车牌颜色编码")
    platecolorcode: Optional[int] = None  # Java: private Integer platecolorcode; // 车牌颜色编码

    # @Excel(name = "车牌颜色")
    platecolor: Optional[str] = None  # Java: private String platecolor; // 车牌颜色

    # @Excel(name = "车牌类型编码")
    platetypecode: Optional[int] = None  # Java: private Integer platetypecode; // 车牌类型编码

    # @Excel(name = "车牌类型")
    platetype: Optional[str] = None  # Java: private String platetype; // 车牌类型

    # @Excel(name = "车牌置信度")
    plateconfidence: Optional[int] = None  # Java: private Integer plateconfidence; // 车牌置信度

    # @Excel(name = "车辆品牌")
    carbrand: Optional[str] = None  # Java: private String carbrand; // 车辆品牌

    # @Excel(name = "车辆颜色编码")
    carcolorcode: Optional[int] = None  # Java: private Integer carcolorcode; // 车辆颜色编码

    # @Excel(name = "车辆颜色")
    carcolor: Optional[str] = None  # Java: private String carcolor; // 车辆颜色

    # @Excel(name = "车辆类型编码")
    cartypecode: Optional[int] = None  # Java: private Integer cartypecode; // 车辆类型编码

    # @Excel(name = "车辆类型")
    cartype: Optional[str] = None  # Java: private String cartype; // 车辆类型

    # @Excel(name = "行驶方向编码")
    cardirectioncode: Optional[int] = None  # Java: private Integer cardirectioncode; // 行驶方向编码

    # @Excel(name = "行驶方向")
    cardirection: Optional[str] = None  # Java: private String cardirection; // 行驶方向

    # @Excel(name = "图片路径")
    snappicturepath: Optional[str] = None  # Java: private String snappicturepath; // 图片路径

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "加载时间", width = 30, dateFormat = "yyyy-MM-dd")
    loadtime: Optional[datetime] = None  # Java: private Date loadtime; // 加载时间

    # @Excel(name = "分类分级")
    gradelevel: Optional[int] = None  # Java: private Integer gradelevel; // 分类分级

    datauuid: Optional[str] = None  # Java: private String datauuid;

    maindirection: Optional[str] = None  # Java: private String maindirection;

    maindirectionname: Optional[str] = None  # Java: private String maindirectionname;

    reserve3: Optional[str] = None  # Java: private String reserve3;

    # @TableField(exist = false)
    query_uuids: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String queryUuids;

    # @TableField(exist = false)
    apply_time1: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String applyTime1; // 时间查询

    # @TableField(exist = false)
    apply_time2: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String applyTime2;

