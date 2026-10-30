# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.OdsSzdnGantryMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsSzdnGantryMapper.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry

__all__ = ["OdsSzdnGantryMapper"]


class OdsSzdnGantryMapper(BaseMapper[OdsSzdnGantry]):
    """门架信息Mapper接口

    【Java→Python】
    1) `public interface OdsSzdnGantryMapper extends BaseMapper<OdsSzdnGantry>` → 继承 BaseMapper[OdsSzdnGantry]；
       Java 侧实现类由 MyBatis-Plus 动态代理生成，Python 侧直接实例化。
    2) `@Repository` → Spring 容器装配；Python 侧由 SpringUtils 注册（见 config 层），
       本类保留注解语义，无运行期副作用。
    3) `List<T>` → `list[T]`；`String` → `str`；`Long` → `int`。
    4) Mapper XML 与接口同名方法一一对应，方法名保持 Java 原样作为 statement id。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(OdsSzdnGantry)

    def selectOdsSzdnGantryById(self, id: str) -> Optional[OdsSzdnGantry]:
        """查询门架信息

        @param id 门架信息ID
        @return 门架信息

        【Java→Python】原方法由 Mapper XML 中的 <select> 实现；
        此处复用 BaseMapper 的内存查询，语义等价于 selectXxxById/selectXxxList。
        """
        return self.selectById(id)

    def selectOdsSzdnGantryList(self, odsSzdnGantry: OdsSzdnGantry) -> list[OdsSzdnGantry]:
        """查询门架信息列表

        @param odsSzdnGantry 门架信息
        @return 门架信息集合

        【Java→Python】原方法由 Mapper XML 中的 <select> 实现；
        此处复用 BaseMapper 的内存查询，语义等价于 selectXxxById/selectXxxList。
        """
        return self.selectList(odsSzdnGantry)
