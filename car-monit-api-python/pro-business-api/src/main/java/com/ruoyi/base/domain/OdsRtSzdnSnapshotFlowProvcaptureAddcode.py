# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsRtSzdnSnapshotFlowProvcaptureAddcode

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsRtSzdnSnapshotFlowProvcaptureAddcode.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsRtSzdnSnapshotFlowProvcaptureAddcode(JavaBean, Custom):
    """省界抓拍对象 ods_rt_szdn_snapshot_flow_provcapture_addcode

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_rt_szdn_snapshot_flow_provcapture_addcode") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_rt_szdn_snapshot_flow_provcapture_addcode"  # @TableName("ods_rt_szdn_snapshot_flow_provcapture_addcode")

    # @TableId(value = "bigId", type = IdType.ASSIGN_UUID)
    big_id: Optional[int] = field(default=None, metadata={"table_id": "bigId", "id_type": "ASSIGN_UUID"})  # Java: private Long bigId;

    deviceip: Optional[str] = None  # Java: private String deviceip;

    tailcapturetimeunix: Optional[int] = None  # Java: private Long tailcapturetimeunix;

    tailcapturetime: Optional[datetime] = None  # Java: private Date tailcapturetime;

    extendattribute: Optional[str] = None  # Java: private String extendattribute;

    smallsideimagewidth: Optional[int] = None  # Java: private Integer smallsideimagewidth;

    axletype: Optional[str] = None  # Java: private String axletype;

    # @Excel(name = "小侧图高度")
    smallsideimageheight: Optional[int] = None  # Java: private Integer smallsideimageheight; // 小侧图高度

    # @Excel(name = "车牌颜色编码")
    platecolorcode: Optional[int] = None  # Java: private Integer platecolorcode; // 车牌颜色编码

    # @Excel(name = "车牌颜色")
    platecolor: Optional[str] = None  # Java: private String platecolor; // 车牌颜色

    # @Excel(name = "遮挡信息")
    cover: Optional[str] = None  # Java: private String cover; // 遮挡信息

    # @Excel(name = "平均可信度")
    averageauthoritative: Optional[int] = None  # Java: private Integer averageauthoritative; // 平均可信度

    # @Excel(name = "车头车道号")
    headlanecode: Optional[int] = None  # Java: private Integer headlanecode; // 车头车道号

    # @Excel(name = "特殊车辆标识")
    specialvehicle: Optional[int] = None  # Java: private Integer specialvehicle; // 特殊车辆标识

    # @Excel(name = "车长")
    carlength: Optional[int] = None  # Java: private Integer carlength; // 车长

    # @Excel(name = "结果类型")
    resulttype: Optional[str] = None  # Java: private String resulttype; // 结果类型

    # @Excel(name = "车高")
    carhight: Optional[int] = None  # Java: private Integer carhight; // 车高

    # @Excel(name = "车型编码")
    carmodelscode: Optional[int] = None  # Java: private Integer carmodelscode; // 车型编码

    # @Excel(name = "车型")
    carmodels: Optional[str] = None  # Java: private String carmodels; // 车型

    # @Excel(name = "车道位置")
    laneposition: Optional[str] = None  # Java: private String laneposition; // 车道位置

    # @Excel(name = "首字可信度")
    firstauthoritative: Optional[int] = None  # Java: private Integer firstauthoritative; // 首字可信度

    # @Excel(name = "车尾车牌图高度")
    tailplateimageheight: Optional[int] = None  # Java: private Integer tailplateimageheight; // 车尾车牌图高度

    # @Excel(name = "车轴数")
    axlecount: Optional[int] = None  # Java: private Integer axlecount; // 车轴数

    # @Excel(name = "车牌图宽度")
    plateimagewidth: Optional[int] = None  # Java: private Integer plateimagewidth; // 车牌图宽度

    # @Excel(name = "特殊类别")
    specialclass: Optional[str] = None  # Java: private String specialclass; // 特殊类别

    # @Excel(name = "车尾车牌号")
    tailplatenumber: Optional[str] = None  # Java: private String tailplatenumber; // 车尾车牌号

    # @Excel(name = "车尾图路径")
    tailimage: Optional[str] = None  # Java: private String tailimage; // 车尾图路径

    # @Excel(name = "车身图采集时间(Unix时间戳)")
    sidecapturetimeunix: Optional[int] = None  # Java: private Long sidecapturetimeunix; // 车身图采集时间(Unix时间戳)

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "车身图采集时间(可读格式)", width = 30, dateFormat = "yyyy-MM-dd")
    sidecapturetime: Optional[datetime] = None  # Java: private Date sidecapturetime; // 车身图采集时间(可读格式)

    # @Excel(name = "车身车道号")
    sidelanecode: Optional[int] = None  # Java: private Integer sidelanecode; // 车身车道号

    # @Excel(name = "轴距")
    wheelbase: Optional[int] = None  # Java: private Integer wheelbase; // 轴距

    # @Excel(name = "附加信息")
    attached: Optional[str] = None  # Java: private String attached; // 附加信息

    # @Excel(name = "车轮数量")
    wheelcount: Optional[int] = None  # Java: private Integer wheelcount; // 车轮数量

    # @Excel(name = "全局唯一标识符")
    guid: Optional[str] = None  # Java: private String guid; // 全局唯一标识符

    # @Excel(name = "车身图宽度")
    sideimagewidth: Optional[int] = None  # Java: private Integer sideimagewidth; // 车身图宽度

    # @Excel(name = "车牌图高度")
    plateimageheight: Optional[int] = None  # Java: private Integer plateimageheight; // 车牌图高度

    # @Excel(name = "数据来源")
    datasource: Optional[str] = None  # Java: private String datasource; // 数据来源

    # @Excel(name = "车辆分类")
    carclass: Optional[str] = None  # Java: private String carclass; // 车辆分类

    # @Excel(name = "门架编号")
    gantryid: Optional[str] = None  # Java: private String gantryid; // 门架编号

    # @Excel(name = "小侧图路径")
    smallsideimage: Optional[str] = None  # Java: private String smallsideimage; // 小侧图路径

    # @Excel(name = "车头图高度")
    headimageheight: Optional[int] = None  # Java: private Integer headimageheight; // 车头图高度

    # @Excel(name = "车侧拍摄场景编码")
    sidescenetypecode: Optional[int] = None  # Java: private Integer sidescenetypecode; // 车侧拍摄场景编码

    # @Excel(name = "车侧拍摄场景")
    sidescenetype: Optional[str] = None  # Java: private String sidescenetype; // 车侧拍摄场景

    # @Excel(name = "车尾图宽度")
    tailimagewidth: Optional[int] = None  # Java: private Integer tailimagewidth; // 车尾图宽度

    # @Excel(name = "环境状态")
    envstate: Optional[str] = None  # Java: private String envstate; // 环境状态

    # @Excel(name = "车头拍摄场景编码")
    headscenetypecode: Optional[int] = None  # Java: private Integer headscenetypecode; // 车头拍摄场景编码

    # @Excel(name = "车头拍摄场景")
    headscenetype: Optional[str] = None  # Java: private String headscenetype; // 车头拍摄场景

    # @Excel(name = "车侧行驶方向编码")
    sidedrivingdirectioncode: Optional[int] = None  # Java: private Integer sidedrivingdirectioncode; // 车侧行驶方向编码

    # @Excel(name = "车侧行驶方向")
    sidedrivingdirection: Optional[str] = None  # Java: private String sidedrivingdirection; // 车侧行驶方向

    # @Excel(name = "车身图高度")
    sideimageheight: Optional[int] = None  # Java: private Integer sideimageheight; // 车身图高度

    # @Excel(name = "车速")
    speed: Optional[str] = None  # Java: private String speed; // 车速

    # @Excel(name = "车尾车牌图路径")
    tailplateimage: Optional[str] = None  # Java: private String tailplateimage; // 车尾车牌图路径

    # @Excel(name = "车头行驶方向编码")
    headdrivingdirectioncode: Optional[int] = None  # Java: private Integer headdrivingdirectioncode; // 车头行驶方向编码

    # @Excel(name = "车头行驶方向")
    headdrivingdirection: Optional[str] = None  # Java: private String headdrivingdirection; // 车头行驶方向

    # @Excel(name = "车辆类型")
    cartype: Optional[str] = None  # Java: private String cartype; // 车辆类型

    # @Excel(name = "车牌图路径")
    plateimage: Optional[str] = None  # Java: private String plateimage; // 车牌图路径

    # @Excel(name = "变道信息")
    changelane: Optional[str] = None  # Java: private String changelane; // 变道信息

    # @Excel(name = "车身图路径")
    sideimage: Optional[str] = None  # Java: private String sideimage; // 车身图路径

    # @Excel(name = "车尾车牌位置")
    tailplateposition: Optional[str] = None  # Java: private String tailplateposition; // 车尾车牌位置

    # @Excel(name = "车头图宽度")
    headimagewidth: Optional[int] = None  # Java: private Integer headimagewidth; // 车头图宽度

    # @Excel(name = "车头图路径")
    headimage: Optional[str] = None  # Java: private String headimage; // 车头图路径

    # @Excel(name = "车重")
    carweight: Optional[int] = None  # Java: private Integer carweight; // 车重

    # @Excel(name = "车尾图高度")
    tailimageheight: Optional[int] = None  # Java: private Integer tailimageheight; // 车尾图高度

    # @Excel(name = "设备编号")
    devicecode: Optional[str] = None  # Java: private String devicecode; // 设备编号

    # @Excel(name = "车牌号码")
    platenumber: Optional[str] = None  # Java: private String platenumber; // 车牌号码

    # @Excel(name = "车尾车牌颜色编码")
    tailplatecolorcode: Optional[int] = None  # Java: private Integer tailplatecolorcode; // 车尾车牌颜色编码

    # @Excel(name = "车尾车牌颜色")
    tailplatecolor: Optional[str] = None  # Java: private String tailplatecolor; // 车尾车牌颜色

    # @Excel(name = "上传时间(Unix时间戳)")
    uploadtimeunix: Optional[int] = None  # Java: private Long uploadtimeunix; // 上传时间(Unix时间戳)

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "上传时间(可读格式)", width = 30, dateFormat = "yyyy-MM-dd")
    uploadtime: Optional[datetime] = None  # Java: private Date uploadtime; // 上传时间(可读格式)

    # @Excel(name = "假轴数")
    impostoraxlecount: Optional[int] = None  # Java: private Integer impostoraxlecount; // 假轴数

    # @Excel(name = "车尾车道号")
    taillanecode: Optional[int] = None  # Java: private Integer taillanecode; // 车尾车道号

    # @Excel(name = "站点ID")
    siteid: Optional[int] = None  # Java: private Integer siteid; // 站点ID

    # @Excel(name = "车头图采集时间(Unix时间戳)")
    headcapturetimeunix: Optional[int] = None  # Java: private Long headcapturetimeunix; // 车头图采集时间(Unix时间戳)

    # @JsonFormat(pattern = "yyyy-MM-dd") @Excel(name = "车头图采集时间(可读格式)", width = 30, dateFormat = "yyyy-MM-dd")
    headcapturetime: Optional[datetime] = None  # Java: private Date headcapturetime; // 车头图采集时间(可读格式)

    # @Excel(name = "车牌位置")
    plateposition: Optional[str] = None  # Java: private String plateposition; // 车牌位置

    # @Excel(name = "车尾车牌图宽度")
    tailplateimagewidth: Optional[int] = None  # Java: private Integer tailplateimagewidth; // 车尾车牌图宽度

    loadtime: Optional[datetime] = None  # Java: private Date loadtime;

    gradelevel: Optional[int] = None  # Java: private Integer gradelevel;

    datauuid: Optional[str] = None  # Java: private String datauuid;

    reserve1: Optional[str] = None  # Java: private String reserve1;

    reserve2: Optional[str] = None  # Java: private String reserve2;

    reserve3: Optional[str] = None  # Java: private String reserve3;

    # @TableField(exist = false)
    query_uuids: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String queryUuids;

