# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.OdsSzdnGantryIpMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsSzdnGantryIpMapper.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.OdsSzdnGantryIp import OdsSzdnGantryIp

__all__ = ["OdsSzdnGantryIpMapper"]


class OdsSzdnGantryIpMapper(BaseMapper[OdsSzdnGantryIp]):
    """省界设备ipMapper接口

    【Java→Python】
    1) `interface ... extends BaseMapper<OdsSzdnGantryIp>` → 继承同名泛型基类。
    2) `Set<String> selectIPSet()`：Java 的 `java.util.Set` → Python 内置 `set[str]`，
       天然去重；注意 **set 无序**，与 Java HashSet 迭代顺序不确定的行为一致。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(OdsSzdnGantryIp)

    def selectOdsSzdnGantryIpById(self, id: int) -> Optional[OdsSzdnGantryIp]:
        """查询省界设备ip

        :param id: 省界设备ipID
        :return: 省界设备ip

        【Java→Python】`Long id` → `int`；复用 BaseMapper 主键查询。
        """
        return self.selectById(id)

    def selectOdsSzdnGantryIpList(self, odsSzdnGantryIp: OdsSzdnGantryIp) -> list[OdsSzdnGantryIp]:
        """查询省界设备ip列表

        :param odsSzdnGantryIp: 省界设备ip
        :return: 省界设备ip集合

        【Java→Python】非空字段等值过滤，等价 XML 的 `<if test="xxx != null">`。
        """
        return self.selectList(odsSzdnGantryIp)

    def selectIPSet(self) -> set[str]:
        """查询全部设备 IP（去重集合）

        :return: 设备 IP 集合

        【Java→Python】对应 SQL 推测为：
            SELECT DISTINCT ip FROM ods_szdn_gantry_ip
        - Java `Set<String>` → Python `set`（两者都去重、都无序）。
        - SQL 的 DISTINCT 会忽略 NULL，这里同样跳过 ip 为空的行。
        - 返回的是**新的 set 副本**，调用方修改不会影响内存表。
        """
        return {
            row.ip
            for row in self._rows
            if row.ip is not None
        }
