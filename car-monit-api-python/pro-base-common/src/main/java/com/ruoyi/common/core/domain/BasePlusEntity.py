# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.domain.BasePlusEntity

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/domain/BasePlusEntity.java
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from com.ruoyi.common.core.domain.CustomClass import CustomClass


@dataclass
class BasePlusEntity(CustomClass):
    """MyBatis-Plus 实体基类（Lombok @Data + @Accessors(chain = true)）。

    【Java→Python】
    1) @Data + @Accessors(chain=true)：setter 返回 this 以支持链式赋值；Python 直接属性赋值，
       没有链式 setter。若要逐行移植链式写法（entity.setId(x).setEpsId(y)），
       可改用 `entity.setId(x)` 返回 self 的显式 setter（本类保留 id 的示例实现）。
    2) java.sql.Timestamp → datetime.datetime（Python 无 Timestamp 类型；
       Timestamp 继承自 java.util.Date，精度到纳秒，datetime 到微秒）。
    3) MyBatis-Plus 注解映射到 dataclass metadata，仅为保留元信息；
       Python 侧的 ORM（如 SQLAlchemy）应使用自己的列定义。
         @TableId(value="id", type=IdType.ASSIGN_UUID)   → metadata={"table_id": ..., "id_type": "ASSIGN_UUID"}
         @TableField(value="eps_id", fill=INSERT)        → metadata={"column": "eps_id", "fill": "INSERT"}
         @TableLogic(value="0", delval="1")              → metadata={"logic": ("0", "1")}
    4) Long → int（Python 的 int 无 32/64 位溢出问题，与 Java long 语义最接近）。
    """

    id: Optional[str] = field(
        default=None, metadata={"table_id": "id", "id_type": "ASSIGN_UUID"}
    )  # 主键
    eps_id: Optional[int] = field(
        default=None, metadata={"column": "eps_id", "fill": "INSERT"}
    )  # 创建人所在单位或科室
    del_flag: Optional[str] = field(
        default=None, metadata={"column": "del_flag", "select": False, "logic": ("0", "1")}
    )  # 删除标志（0存在 1删除）
    create_by: Optional[int] = field(
        default=None, metadata={"column": "create_by", "fill": "INSERT"}
    )  # 创建人
    create_time: Optional[datetime] = field(
        default=None, metadata={"column": "create_time", "fill": "INSERT", "json_format": "yyyy-MM-dd HH:mm:ss"}
    )  # 创建时间
    update_by: Optional[int] = field(
        default=None, metadata={"column": "update_by", "fill": "UPDATE"}
    )  # 更新人
    update_time: Optional[datetime] = field(
        default=None, metadata={"column": "update_time", "fill": "UPDATE", "json_format": "yyyy-MM-dd HH:mm:ss"}
    )  # 更新时间
    sort: Optional[int] = None  # 排序
    tenant_id: Optional[int] = field(
        default=None, metadata={"column": "tenant_id", "fill": "INSERT"}
    )  # 租户

    def setId(self, value: Optional[str]) -> "BasePlusEntity":
        """@Accessors(chain=true) 的链式 setter 示例（Java: return this）。"""
        self.id = value
        return self
