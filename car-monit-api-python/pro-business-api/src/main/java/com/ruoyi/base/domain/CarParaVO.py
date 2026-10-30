# -*- coding: utf-8 -*-
"""com.ruoyi.base.domain.CarParaVO

源文件：pro-business-api/src/main/java/com/ruoyi/base/domain/CarParaVO.java
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from com.ruoyi.common.core.domain.JavaBean import JavaBean


@dataclass
class CarParaVO(JavaBean):
    """CarParaVO

    【Java→Python】
    1) Lombok @Data → @dataclass；getXxx()/setXxx()/isXxx() 由 JavaBean 动态提供
       （含 @Accessors(chain = true) 的链式 setter，返回 self）。
    2) 无 @TableName（非表实体 / VO / DTO）。
    3) @TableId/@TableField → dataclass field(metadata=...)，仅保留元信息；
       Java 的 Long → int、BigDecimal → float、Date/Timestamp → datetime。
    """
    carlist: Optional[list[Any]] = None  # Java: private List<CarVO> carlist; // 车俩列表

    car_no: Optional[str] = None  # Java: private String carNo; // 车牌号

    apply_time1: Optional[str] = None  # Java: private String applyTime1; // 时间查询

    apply_time2: Optional[str] = None  # Java: private String applyTime2;

    car_no_list: Optional[list[str]] = None  # Java: private List<String> carNoList; // 车俩编号数组

    page_num: Optional[int] = None  # Java: private Integer pageNum; // 当前页面

    page_size: Optional[int] = None  # Java: private Integer pageSize; // 分页大小

    start_num: Optional[int] = None  # Java: private Integer startNum; // 起始界面

    end_num: Optional[int] = None  # Java: private Integer endNum; // 最后的界面

    star_time: Optional[int] = None  # Java: private Integer starTime; // 起始天数

    end_time: Optional[int] = None  # Java: private Integer endTime; // 最后的天数

    flag: Optional[str] = None  # Java: private String flag; // 标识位

    last_exit_time: Optional[datetime] = None  # Java: private Date lastExitTime; // 游标分页的最后出站时间（用于游标分页）

    # 【Java→Python】Java 源 L57 无访问修饰符（包级私有）`List<String> sectionList;`。
    # Lombok 同样会为这种字段生成 getter/setter，Python 侧必须保留成 dataclass 字段。
    section_list: Optional[list[str]] = None  # Java: List<String> sectionList; // 对象集合

