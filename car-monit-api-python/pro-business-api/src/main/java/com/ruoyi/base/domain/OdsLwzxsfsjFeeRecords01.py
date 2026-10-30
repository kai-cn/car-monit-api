# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.OdsLwzxsfsjFeeRecords01

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/OdsLwzxsfsjFeeRecords01.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class OdsLwzxsfsjFeeRecords01(JavaBean, Custom):
    """基础-收费流水对象 ods_lwzxsfsj_fee_records_01

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("ods_lwzxsfsj_fee_records_01") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "ods_lwzxsfsj_fee_records_01"  # @TableName("ods_lwzxsfsj_fee_records_01")

    # @TableId(value = "big_id", type = IdType.ASSIGN_UUID)
    big_id: Optional[str] = field(default=None, metadata={"table_id": "big_id", "id_type": "ASSIGN_UUID"})  # Java: private String bigId; // 主键

    # @Excel(name = "算法标识")
    algorithmidentifier: Optional[str] = None  # Java: private String algorithmidentifier; // 算法标识

    # @Excel(name = "天线ID编号(天线头编号)")
    antennaid: Optional[str] = None  # Java: private String antennaid; // 天线ID编号(天线头编号)

    # @Excel(name = "车轴数")
    axlecount: Optional[int] = None  # Java: private Long axlecount; // 车轴数

    # @Excel(name = "交易后余额")
    balanceafter: Optional[float] = None  # Java: private BigDecimal balanceafter; // 交易后余额

    # @Excel(name = "交易前余额")
    balancebefore: Optional[float] = None  # Java: private BigDecimal balancebefore; // 交易前余额

    # @Excel(name = "本次交易后卡片累计金额")
    cardfeesumafter: Optional[float] = None  # Java: private BigDecimal cardfeesumafter; // 本次交易后卡片累计金额

    # @Excel(name = "本次交易前卡片累计金额")
    cardfeesumbefore: Optional[float] = None  # Java: private BigDecimal cardfeesumbefore; // 本次交易前卡片累计金额

    # @Excel(name = "控制器序号")
    computerorder: Optional[str] = None  # Java: private String computerorder; // 控制器序号

    # @Excel(name = "交易耗时", readConverterExp = "单=位：ms")
    consumetime: Optional[int] = None  # Java: private Long consumetime; // 交易耗时（单位：ms）

    # @Excel(name = "CPU卡编号")
    cpucardid: Optional[str] = None  # Java: private String cpucardid; // CPU卡编号

    # @Excel(name = "CPU卡类型")
    cpucardtype: Optional[str] = None  # Java: private String cpucardtype; // CPU卡类型

    # @Excel(name = "CPU截止日期")
    cpuenddate: Optional[str] = None  # Java: private String cpuenddate; // CPU截止日期

    # @Excel(name = "CPU卡片发行方标识")
    cpuissueid: Optional[str] = None  # Java: private String cpuissueid; // CPU卡片发行方标识

    # @Excel(name = "CPU卡片网络编号")
    cpunetid: Optional[str] = None  # Java: private String cpunetid; // CPU卡片网络编号

    # @Excel(name = "CPU起始日期")
    cpustartdate: Optional[str] = None  # Java: private String cpustartdate; // CPU起始日期

    # @Excel(name = "CPU 内车牌号码")
    cpuvehicleplate: Optional[str] = None  # Java: private String cpuvehicleplate; // CPU 内车牌号码

    # @Excel(name = "CPU内车型")
    cpuvehicletype: Optional[str] = None  # Java: private String cpuvehicletype; // CPU内车型

    # @Excel(name = "CPU用户卡版本号")
    cpuversion: Optional[str] = None  # Java: private String cpuversion; // CPU用户卡版本号

    # @Excel(name = "处理状态")
    dealstatus: Optional[str] = None  # Java: private String dealstatus; // 处理状态

    # @Excel(name = "优惠金额")
    discountfee: Optional[float] = None  # Java: private BigDecimal discountfee; // 优惠金额

    # @Excel(name = "优惠金额组合")
    discountfeegroup: Optional[str] = None  # Java: private String discountfeegroup; // 优惠金额组合

    # @Excel(name = "入口车道类型")
    enlanetype: Optional[str] = None  # Java: private String enlanetype; // 入口车道类型

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "进站时间", width = 30, dateFormat = "yyyy-MM-dd  HH:mm:ss")
    entime: Optional[datetime] = None  # Java: private Date entime; // 进站时间

    # @Excel(name = "进站收费站车道号")
    entolllaneid: Optional[str] = None  # Java: private String entolllaneid; // 进站收费站车道号

    # @Excel(name = "进站收费站hex编码")
    entollstationhex: Optional[str] = None  # Java: private String entollstationhex; // 进站收费站hex编码

    # @Excel(name = "费用")
    fee: Optional[float] = None  # Java: private BigDecimal fee; // 费用

    # @Excel(name = "计费模块响应计费结果")
    feecalcresult: Optional[str] = None  # Java: private String feecalcresult; // 计费模块响应计费结果 0 成功 1 失败

    # @Excel(name = "计费接口特情值")
    feecalcspecial: Optional[str] = None  # Java: private String feecalcspecial; // 计费接口特情值

    # @Excel(name = "计费特情值组合")
    feecalcspecials: Optional[str] = None  # Java: private String feecalcspecials; // 计费特情值组合

    # @Excel(name = "交易金额组合")
    feegroup: Optional[str] = None  # Java: private String feegroup; // 交易金额组合

    # @Excel(name = "计费信息1")
    feeinfo1: Optional[str] = None  # Java: private String feeinfo1; // 计费信息1

    # @Excel(name = "计费信息2")
    feeinfo2: Optional[str] = None  # Java: private String feeinfo2; // 计费信息2

    # @Excel(name = "计费信息3")
    feeinfo3: Optional[str] = None  # Java: private String feeinfo3; // 计费信息3

    # @Excel(name = "收费里程")
    feemileage: Optional[float] = None  # Java: private BigDecimal feemileage; // 收费里程

    # @Excel(name = "本省计费起点")
    feeprovbeginhex: Optional[str] = None  # Java: private String feeprovbeginhex; // 本省计费起点

    # @Excel(name = "计费协议保留字段1")
    feespare1: Optional[str] = None  # Java: private String feespare1; // 计费协议保留字段1

    # @Excel(name = "计费协议保留字段2")
    feespare2: Optional[str] = None  # Java: private String feespare2; // 计费协议保留字段2

    # @Excel(name = "计费车型")
    feevehicletype: Optional[str] = None  # Java: private String feevehicletype; // 计费车型

    # @Excel(name = "门架Hex值")
    gantryhex: Optional[str] = None  # Java: private String gantryhex; // 门架Hex值

    # @Excel(name = "对向门架Hex值")
    gantryhexopposite: Optional[str] = None  # Java: private String gantryhexopposite; // 对向门架Hex值

    # @Excel(name = "门架编码")
    gantryid: Optional[str] = None  # Java: private String gantryid; // 门架编码

    # @Excel(name = "门架顺序号")
    gantryordernum: Optional[int] = None  # Java: private Long gantryordernum; // 门架顺序号

    # @Excel(name = "门架类型")
    gantrytype: Optional[str] = None  # Java: private String gantrytype; // 门架类型

    # @Excel(name = "节假日状态")
    holidaystate: Optional[str] = None  # Java: private String holidaystate; // 节假日状态

    # @Excel(name = "小时批次号")
    hourbatchno: Optional[str] = None  # Java: private String hourbatchno; // 小时批次号

    # @Excel(name = "消费密钥版本号")
    keyversion: Optional[str] = None  # Java: private String keyversion; // 消费密钥版本号

    # @Excel(name = "上一个门架的hex编号")
    lastgantryhex: Optional[str] = None  # Java: private String lastgantryhex; // 上一个门架的hex编号

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "通过上一个门架的时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    lastgantrytime: Optional[datetime] = None  # Java: private Date lastgantrytime; // 通过上一个门架的时间

    # @Excel(name = "匹配状态")
    matchstatus: Optional[str] = None  # Java: private String matchstatus; // 匹配状态

    # @Excel(name = "通行介质类型")
    mediatype: Optional[str] = None  # Java: private String mediatype; // 通行介质类型

    # @Excel(name = "本次交易后累计无卡次数")
    nocardtimesafter: Optional[int] = None  # Java: private Long nocardtimesafter; // 本次交易后累计无卡次数

    # @Excel(name = "本次交易前累计无卡次数")
    nocardtimesbefore: Optional[int] = None  # Java: private Long nocardtimesbefore; // 本次交易前累计无卡次数

    # @Excel(name = "OBU/CPC卡电量百分比")
    obuelectrical: Optional[int] = None  # Java: private Long obuelectrical; // OBU/CPC卡电量百分比

    # @Excel(name = "OBU/CPC截止日期")
    obuenddate: Optional[str] = None  # Java: private String obuenddate; // OBU/CPC截止日期

    # @Excel(name = "本次交易后标签累计实收金额")
    obufeesumafter: Optional[float] = None  # Java: private BigDecimal obufeesumafter; // 本次交易后标签累计实收金额

    # @Excel(name = "本次交易前标签累计实收金额")
    obufeesumbefore: Optional[float] = None  # Java: private BigDecimal obufeesumbefore; // 本次交易前标签累计实收金额

    # @Excel(name = "读取标签入口信息类型")
    obuinfotyperead: Optional[str] = None  # Java: private String obuinfotyperead; // 读取标签入口信息类型

    # @Excel(name = "本次写入标签入口信息类型")
    obuinfotypewrite: Optional[str] = None  # Java: private String obuinfotypewrite; // 本次写入标签入口信息类型

    # @Excel(name = "OBU/CPC发行方标识")
    obuissueid: Optional[str] = None  # Java: private String obuissueid; // OBU/CPC发行方标识

    # @Excel(name = "OBU中上一个门架HEX")
    obulastgantryhex: Optional[str] = None  # Java: private String obulastgantryhex; // OBU中上一个门架HEX

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "OBU中通过上一个门架时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    obulastgantrytime: Optional[datetime] = None  # Java: private Date obulastgantrytime; // OBU中通过上一个门架时间

    # @Excel(name = "OBU /CPC物理地址")
    obumac: Optional[str] = None  # Java: private String obumac; // OBU /CPC物理地址

    # @Excel(name = "本次交易后标签累计里程")
    obumileageafter: Optional[float] = None  # Java: private BigDecimal obumileageafter; // 本次交易后标签累计里程

    # @Excel(name = "本次交易前标签累计里程")
    obumileagebefore: Optional[float] = None  # Java: private BigDecimal obumileagebefore; // 本次交易前标签累计里程

    # @Excel(name = "标签入口状态")
    obupassstate: Optional[str] = None  # Java: private String obupassstate; // 标签入口状态

    # @Excel(name = "本次交易后标签累计应收金额")
    obupayfeesumafter: Optional[float] = None  # Java: private BigDecimal obupayfeesumafter; // 本次交易后标签累计应收金额

    # @Excel(name = "本次交易前标签累计应收金额")
    obupayfeesumbefore: Optional[float] = None  # Java: private BigDecimal obupayfeesumbefore; // 本次交易前标签累计应收金额

    # @Excel(name = "本次交易后标签累计金额", readConverterExp = "省=内")
    obuprovfeesumafter: Optional[float] = None  # Java: private BigDecimal obuprovfeesumafter; // 本次交易后标签累计金额（省内）

    # @Excel(name = "本次交易前标签累计金额 ", readConverterExp = "省=内")
    obuprovfeesumbefore: Optional[float] = None  # Java: private BigDecimal obuprovfeesumbefore; // 本次交易前标签累计金额 （省内）

    # @Excel(name = "本次交易后标签累计应收金额", readConverterExp = "省=内")
    obuprovpayfeesumafter: Optional[float] = None  # Java: private BigDecimal obuprovpayfeesumafter; // 本次交易后标签累计应收金额（省内）

    # @Excel(name = "本次交易前标签累计应收金额", readConverterExp = "省=内")
    obuprovpayfeesumbefore: Optional[float] = None  # Java: private BigDecimal obuprovpayfeesumbefore; // 本次交易前标签累计应收金额（省内）

    # @Excel(name = "省内本次交易后标签累计写入成功数量")
    obuprovtradesuccnumafter: Optional[int] = None  # Java: private Long obuprovtradesuccnumafter; // 省内本次交易后标签累计写入成功数量

    # @Excel(name = "省内本次交易前标签累计写入成功数量")
    obuprovtradesuccnumbefore: Optional[int] = None  # Java: private Long obuprovtradesuccnumbefore; // 省内本次交易前标签累计写入成功数量

    # @Excel(name = "OBU 单/双片标识")
    obusign: Optional[str] = None  # Java: private String obusign; // OBU 单/双片标识

    # @Excel(name = "OBU/CPC序号编码")
    obusn: Optional[str] = None  # Java: private String obusn; // OBU/CPC序号编码

    # @Excel(name = "OBU/CPC起始日期")
    obustartdate: Optional[str] = None  # Java: private String obustartdate; // OBU/CPC起始日期

    # @Excel(name = "OBU/CPC状态")
    obustate: Optional[str] = None  # Java: private String obustate; // OBU/CPC状态

    # @Excel(name = "本次交易后标签累计写入成功总量")
    obutotaltradesuccnumafter: Optional[int] = None  # Java: private Long obutotaltradesuccnumafter; // 本次交易后标签累计写入成功总量

    # @Excel(name = "本次交易前标签累计写入成功总量")
    obutotaltradesuccnumbefore: Optional[int] = None  # Java: private Long obutotaltradesuccnumbefore; // 本次交易前标签累计写入成功总量

    # @Excel(name = "标签写入结果")
    obutraderesult: Optional[str] = None  # Java: private String obutraderesult; // 标签写入结果

    # @Excel(name = "obu车牌")
    obuvehicleplate: Optional[str] = None  # Java: private String obuvehicleplate; // obu车牌

    # @Excel(name = "obu车牌类型")
    obuvehicletype: Optional[str] = None  # Java: private String obuvehicletype; // obu车牌类型

    # @Excel(name = "OBU/CPC版本号")
    obuversion: Optional[str] = None  # Java: private String obuversion; // OBU/CPC版本号

    # @Excel(name = "参数")
    params: Optional[str] = None  # Java: private String params; // 参数

    # @Excel(name = "通行id")
    passid: Optional[str] = None  # Java: private String passid; // 通行id

    # @Excel(name = "通行状态")
    passstate: Optional[str] = None  # Java: private String passstate; // 通行状态

    # @Excel(name = "本次计费拟合结果标识")
    pathfitflag: Optional[str] = None  # Java: private String pathfitflag; // 本次计费拟合结果标识

    # @Excel(name = "应收金额")
    payfee: Optional[float] = None  # Java: private BigDecimal payfee; // 应收金额

    # @Excel(name = "应收金额组合")
    payfeegroup: Optional[str] = None  # Java: private String payfeegroup; // 应收金额组合

    # @Excel(name = "PC-RSU接口协议版本号")
    pcrsuversion: Optional[str] = None  # Java: private String pcrsuversion; // PC-RSU接口协议版本号

    # @Excel(name = "本省累计通行金额参考")
    provminfee: Optional[float] = None  # Java: private BigDecimal provminfee; // 本省累计通行金额参考

    # @Excel(name = "本次交易后累计省份数量")
    provincenumafter: Optional[int] = None  # Java: private Long provincenumafter; // 本次交易后累计省份数量

    # @Excel(name = "本次交易前累计省份数量")
    provincenumbefore: Optional[int] = None  # Java: private Long provincenumbefore; // 本次交易前累计省份数量

    # @Excel(name = "计费模块计费模式")
    ratecompute: Optional[str] = None  # Java: private String ratecompute; // 计费模块计费模式

    # @Excel(name = "计费模块拟合点总数")
    ratefitcount: Optional[int] = None  # Java: private Long ratefitcount; // 计费模块拟合点总数

    # @Excel(name = "计费模块和计费参数版本号")
    rateversion: Optional[str] = None  # Java: private String rateversion; // 计费模块和计费参数版本号

    # @Excel(name = "本次交易读取的EF04加密摘要验证结果")
    readciphertextverify: Optional[str] = None  # Java: private String readciphertextverify; // 本次交易读取的EF04加密摘要验证结果

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "接收时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    receivetime: Optional[datetime] = None  # Java: private Date receivetime; // 接收时间

    # @Excel(name = "交易的服务类型")
    servicetype: Optional[str] = None  # Java: private String servicetype; // 交易的服务类型

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "门架后台入库时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    stationdbtime: Optional[datetime] = None  # Java: private Date stationdbtime; // 门架后台入库时间

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "门架后台处理时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    stationdealtime: Optional[datetime] = None  # Java: private Date stationdealtime; // 门架后台处理时间

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "门架后台匹配时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    stationmatchtime: Optional[datetime] = None  # Java: private Date stationmatchtime; // 门架后台匹配时间

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "门架后台去重时间", width = 30, dateFormat = "yyyy-MM-dd HH:mm:ss")
    stationvalidtime: Optional[datetime] = None  # Java: private Date stationvalidtime; // 门架后台去重时间

    # @Excel(name = "TAC码")
    tac: Optional[str] = None  # Java: private String tac; // TAC码

    # @Excel(name = "终端机编号")
    terminalno: Optional[str] = None  # Java: private String terminalno; // 终端机编号

    # @Excel(name = "PSAM卡脱机交易序列号")
    terminaltransno: Optional[str] = None  # Java: private String terminaltransno; // PSAM卡脱机交易序列号

    # @Excel(name = "收费单元编号组合")
    tollintervalid: Optional[str] = None  # Java: private String tollintervalid; // 收费单元编号组合

    # @Excel(name = "收费单元处理标识")
    tollintervalsign: Optional[str] = None  # Java: private String tollintervalsign; // 收费单元处理标识

    # @Excel(name = "车货总重")
    totalweight: Optional[float] = None  # Java: private BigDecimal totalweight; // 车货总重

    # @Excel(name = "计费交易编号")
    tradeid: Optional[str] = None  # Java: private String tradeid; // 计费交易编号

    # @Excel(name = "本次交易读取的EF04加密摘要")
    tradereadciphertext: Optional[str] = None  # Java: private String tradereadciphertext; // 本次交易读取的EF04加密摘要

    # @Excel(name = "卡片复合交易结果")
    traderesult: Optional[str] = None  # Java: private String traderesult; // 卡片复合交易结果

    # @Excel(name = "交易类型")
    tradetype: Optional[str] = None  # Java: private String tradetype; // 交易类型

    # @Excel(name = "本次交易生成的EF04加密摘要")
    tradewriteciphertext: Optional[str] = None  # Java: private String tradewriteciphertext; // 本次交易生成的EF04加密摘要

    # @Excel(name = "卡面扣费金额")
    transfee: Optional[float] = None  # Java: private BigDecimal transfee; // 卡面扣费金额

    # @Excel(name = "IC卡交易序号")
    transno: Optional[str] = None  # Java: private String transno; // IC卡交易序号

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "计费交易时间", width = 30, dateFormat = "yyyy-MM-dd")
    transtime: Optional[datetime] = None  # Java: private Date transtime; // 计费交易时间

    # @Excel(name = "交易类型标识")
    transtype: Optional[str] = None  # Java: private String transtype; // 交易类型标识

    # @Excel(name = "去重状态")
    validstatus: Optional[str] = None  # Java: private String validstatus; // 去重状态

    # @Excel(name = "车种")
    vehicleclass: Optional[str] = None  # Java: private String vehicleclass; // 车种

    # @Excel(name = "车高")
    vehiclehight: Optional[float] = None  # Java: private BigDecimal vehiclehight; // 车高

    # @Excel(name = "车长")
    vehiclelength: Optional[float] = None  # Java: private BigDecimal vehiclelength; // 车长

    # @Excel(name = "车牌号+类型")
    vehicleplate: Optional[str] = None  # Java: private String vehicleplate; // 车牌号+类型

    # @Excel(name = "车辆座位数/载重")
    vehicleseat: Optional[str] = None  # Java: private String vehicleseat; // 车辆座位数/载重

    # @Excel(name = "车辆状态标识")
    vehiclesign: Optional[str] = None  # Java: private String vehiclesign; // 车辆状态标识

    # @Excel(name = "车辆类型")
    vehicletype: Optional[str] = None  # Java: private String vehicletype; // 车辆类型

    # @Excel(name = "车辆用户类型")
    vehicleusertype: Optional[str] = None  # Java: private String vehicleusertype; // 车辆用户类型

    # @Excel(name = "车宽")
    vehiclewidth: Optional[float] = None  # Java: private BigDecimal vehiclewidth; // 车宽

    # @Excel(name = "校验码")
    verifycode: Optional[str] = None  # Java: private String verifycode; // 校验码

    # @JsonFormat(pattern = "yyyy-MM-dd HH:mm:ss") @Excel(name = "加载时间", width = 30, dateFormat = "yyyy-MM-dd")
    load_time: Optional[datetime] = None  # Java: private Date loadTime; // 加载时间

    # @Excel(name = "分类分级")
    grade_level: Optional[int] = None  # Java: private Long gradeLevel; // 分类分级

    # @Excel(name = "cid")
    cid: Optional[str] = None  # Java: private String cid; // cid

    # @TableField(exist = false)
    cid_list: Optional[list[str]] = field(default=None, metadata={"exist": False})  # Java: private List<String> cidList;

    # @TableField(exist = false)
    in_apply_time1: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String inApplyTime1; // 时间查询

    # @TableField(exist = false)
    in_apply_time2: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String inApplyTime2;

    # @TableField(exist = false)
    out_apply_time1: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String outApplyTime1;

    # @TableField(exist = false)
    out_apply_time2: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String outApplyTime2;

    # @TableField(exist = false)
    plate_color: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String plateColor; // 车牌类型

    # @TableField(exist = false)
    gantry_name: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String gantryName; // 门架名称

    # @TableField(exist = false)
    flag: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String flag; // 标识位

    # @TableField(exist = false)
    section_code_str: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String sectionCodeStr; // 所属路段编码

    # @TableField(exist = false)
    type: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String type; // 1收费站、2门架、3服务区

    # @TableField(exist = false)
    code: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String code; // 编码

    # @TableField(exist = false)
    transtime_str: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String transtimeStr; // 计费交易时间

    # @TableField(exist = false)
    lastgantrytime_str: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String lastgantrytimeStr; // 通过上一个门架的时间

    # @TableField(exist = false)
    start_num: Optional[int] = field(default=None, metadata={"exist": False})  # Java: private Integer startNum; // 起始界面

    # @TableField(exist = false)
    end_num: Optional[int] = field(default=None, metadata={"exist": False})  # Java: private Integer endNum; // 最后的界面

    # @TableField(exist = false)
    sectioncode: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String sectioncode; // 路段编码

    # @TableField(exist = false)
    order_by_flag: Optional[str] = field(default=None, metadata={"exist": False})  # Java: private String orderByFlag; // 排序

    # 【Java→Python】Java 源 L621/L627 无访问修饰符（包级私有）字段，Lombok 仍生成访问器。
    # @TableField(exist = false)
    code_list: Optional[list[str]] = field(default=None, metadata={"exist": False})  # Java: List<String> codeList;

    # @TableField(exist = false)
    section_list: Optional[list[str]] = field(default=None, metadata={"exist": False})  # Java: List<String> sectionList;

