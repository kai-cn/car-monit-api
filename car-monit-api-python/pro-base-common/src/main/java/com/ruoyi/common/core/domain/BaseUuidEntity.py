# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.domain.BaseUuidEntity

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/domain/BaseUuidEntity.java
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from com.ruoyi.common.core.domain.CustomClass import CustomClass


@dataclass
class BaseUuidEntity(CustomClass):
    """UUID 主键实体基类（手写 getter/setter）。

    【Java→Python】
    1) java.sql.Timestamp → datetime.datetime。
    2) Map<String,Object> params → dict；注意 Java 的 getParams() 直接返回字段（可能是 null），
       不做懒创建——这一点与 BaseEntity.getParams() 不同，原样保留。
    3) 手写 getXxx/setXxx → 属性访问；为便于逐行对照，保留同名方法。
    """

    id: Optional[str] = None                 # 主键
    eps_id: Optional[int] = None             # 创建人所在单位或科室
    del_flag: Optional[str] = None           # 删除标志（0存在 1删除）
    create_by: Optional[int] = None          # 创建人
    create_time: Optional[datetime] = None   # 创建时间
    update_by: Optional[int] = None          # 更新人
    update_time: Optional[datetime] = None   # 更新时间
    sort: Optional[int] = None               # 排序
    remark: Optional[str] = None             # 备注
    tenant_id: Optional[int] = None          # 租户
    dept_sub_code: Optional[str] = None      # 部门编码

    # ---- 其他通用字段
    flag: Optional[str] = None               # 标志
    search_value: Optional[str] = None       # 搜索值
    params: Optional[dict[str, Any]] = None  # 请求参数

    def getId(self) -> Optional[str]:
        return self.id

    def setId(self, value: Optional[str]) -> None:
        self.id = value

    def getEpsId(self) -> Optional[int]:
        return self.eps_id

    def setEpsId(self, value: Optional[int]) -> None:
        self.eps_id = value

    def getDelFlag(self) -> Optional[str]:
        return self.del_flag

    def setDelFlag(self, value: Optional[str]) -> None:
        self.del_flag = value

    def getCreateBy(self) -> Optional[int]:
        return self.create_by

    def setCreateBy(self, value: Optional[int]) -> None:
        self.create_by = value

    def getCreateTime(self) -> Optional[datetime]:
        return self.create_time

    def setCreateTime(self, value: Optional[datetime]) -> None:
        self.create_time = value

    def getUpdateBy(self) -> Optional[int]:
        return self.update_by

    def setUpdateBy(self, value: Optional[int]) -> None:
        self.update_by = value

    def getUpdateTime(self) -> Optional[datetime]:
        return self.update_time

    def setUpdateTime(self, value: Optional[datetime]) -> None:
        self.update_time = value

    def getSort(self) -> Optional[int]:
        return self.sort

    def setSort(self, value: Optional[int]) -> None:
        self.sort = value

    def getRemark(self) -> Optional[str]:
        return self.remark

    def setRemark(self, value: Optional[str]) -> None:
        self.remark = value

    def getFlag(self) -> Optional[str]:
        return self.flag

    def setFlag(self, value: Optional[str]) -> None:
        self.flag = value

    def getSearchValue(self) -> Optional[str]:
        return self.search_value

    def setSearchValue(self, value: Optional[str]) -> None:
        self.search_value = value

    def getParams(self) -> Optional[dict[str, Any]]:
        # 【Java→Python】这里不做懒创建，保持 Java 原实现（可能返回 null）
        return self.params

    def setParams(self, value: Optional[dict[str, Any]]) -> None:
        self.params = value

    def getTenantId(self) -> Optional[int]:
        return self.tenant_id

    def setTenantId(self, value: Optional[int]) -> None:
        self.tenant_id = value

    def getDeptSubCode(self) -> Optional[str]:
        return self.dept_sub_code

    def setDeptSubCode(self, value: Optional[str]) -> None:
        self.dept_sub_code = value
