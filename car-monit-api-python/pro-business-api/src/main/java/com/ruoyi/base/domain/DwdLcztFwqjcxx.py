# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.DwdLcztFwqjcxx

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/DwdLcztFwqjcxx.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean
from com.ruoyi.common.core.domain.Custom import Custom


@dataclass
class DwdLcztFwqjcxx(JavaBean, Custom):
    """服务区基础信息对象 dwd_lczt_fwqjcxx

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) @TableName("dwd_lczt_fwqjcxx") → 类属性 TABLE_NAME（MyBatis-Plus 表名元信息）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    4) @Accessors(chain = true)：setter 返回 this，JavaBean 已实现。
    """
    TABLE_NAME = "dwd_lczt_fwqjcxx"  # @TableName("dwd_lczt_fwqjcxx")

    # @TableId(value = "agent_pk", type = IdType.ASSIGN_UUID)
    agent_pk: Optional[str] = field(default=None, metadata={"table_id": "agent_pk", "id_type": "ASSIGN_UUID"})  # Java: private String agentPk; // 代理主键

    # @Excel(name = "源系统主键")
    yxtzj: Optional[str] = None  # Java: private String yxtzj; // 源系统主键

    # @Excel(name = "服务区编码")
    fwqbm: Optional[str] = None  # Java: private String fwqbm; // 服务区编码

    # @Excel(name = "服务区名称")
    fwqmc: Optional[str] = None  # Java: private String fwqmc; // 服务区名称

    # @Excel(name = "纬度")
    wd: Optional[str] = None  # Java: private String wd; // 纬度

    # @Excel(name = "方向名称")
    fxmc: Optional[str] = None  # Java: private String fxmc; // 方向名称

    # @Excel(name = "方向代码")
    fxdm: Optional[str] = None  # Java: private String fxdm; // 方向代码

    # @Excel(name = "经度")
    jd: Optional[str] = None  # Java: private String jd; // 经度

    # @Excel(name = "所属路线编号")
    sslxbh: Optional[str] = None  # Java: private String sslxbh; // 所属路线编号

    # @Excel(name = "所属路线名称")
    sslxmc: Optional[str] = None  # Java: private String sslxmc; // 所属路线名称

    # @Excel(name = "所属路段编号")
    ssldbh: Optional[str] = None  # Java: private String ssldbh; // 所属路段编号

    # @Excel(name = "所属路段名称")
    ssldmc: Optional[str] = None  # Java: private String ssldmc; // 所属路段名称

    # @Excel(name = "所处桩号(K格式)")
    sczhkgs: Optional[str] = None  # Java: private String sczhkgs; // 所处桩号(K格式)

    # @Excel(name = "所处桩号(数值格式)")
    sczhszgs: Optional[str] = None  # Java: private String sczhszgs; // 所处桩号(数值格式)

    # @Excel(name = "所属管理中心编码")
    ssglzxbm: Optional[str] = None  # Java: private String ssglzxbm; // 所属管理中心编码

    # @Excel(name = "所属管理中心名称")
    ssglzxmc: Optional[str] = None  # Java: private String ssglzxmc; // 所属管理中心名称

    # @Excel(name = "行政区划名称")
    xzqhmc: Optional[str] = None  # Java: private String xzqhmc; // 行政区划名称

    # @Excel(name = "营业日期")
    yyrq: Optional[str] = None  # Java: private String yyrq; // 营业日期

    # @Excel(name = "车位数")
    cws: Optional[str] = None  # Java: private String cws; // 车位数

    # @Excel(name = "是否设置了卡口")
    sfszlkk: Optional[str] = None  # Java: private String sfszlkk; // 是否设置了卡口

    # @Excel(name = "充电桩数")
    cdzs: Optional[str] = None  # Java: private String cdzs; // 充电桩数

    # @Excel(name = "是否餐饮服务")
    sfcyfw: Optional[str] = None  # Java: private String sfcyfw; // 是否餐饮服务

    # @Excel(name = "是否提供住宿服务")
    sftgzsfw: Optional[str] = None  # Java: private String sftgzsfw; // 是否提供住宿服务

    # @Excel(name = "是否提供汽修服务")
    sftgqxfw: Optional[str] = None  # Java: private String sftgqxfw; // 是否提供汽修服务

    # @Excel(name = "是否提供超市服务")
    sftgcsfw: Optional[str] = None  # Java: private String sftgcsfw; // 是否提供超市服务

    # @Excel(name = "是否提供加油服务")
    sftgjyfw: Optional[str] = None  # Java: private String sftgjyfw; // 是否提供加油服务

    # @Excel(name = "面积(平方米)")
    mj: Optional[str] = None  # Java: private String mj; // 面积(平方米)

    # @Excel(name = "是否提供厕所服务")
    sftgcshfw: Optional[str] = None  # Java: private String sftgcshfw; // 是否提供厕所服务

    # @Excel(name = "行政区划代码")
    xzqhdm: Optional[str] = None  # Java: private String xzqhdm; // 行政区划代码

    # @Excel(name = "使用年限")
    synx: Optional[str] = None  # Java: private String synx; // 使用年限

    # @Excel(name = "来源系统")
    lyxt: Optional[str] = None  # Java: private String lyxt; // 来源系统

    # @Excel(name = "加载日期")
    load_time: Optional[str] = None  # Java: private String loadTime; // 加载日期

    # @Excel(name = "全字段MD5")
    all_col_pk: Optional[str] = None  # Java: private String allColPk; // 全字段MD5

