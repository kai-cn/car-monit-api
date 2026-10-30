# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.OdsLwzxsfsjFeeStationEnter01Mapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsLwzxsfsjFeeStationEnter01Mapper.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.OdsLwzxsfsjFeeStationEnter01 import OdsLwzxsfsjFeeStationEnter01

__all__ = ["OdsLwzxsfsjFeeStationEnter01Mapper"]


class OdsLwzxsfsjFeeStationEnter01Mapper(BaseMapper[OdsLwzxsfsjFeeStationEnter01]):
    """收费站入口数据Mapper接口

    【Java→Python】
    1) `public interface OdsLwzxsfsjFeeStationEnter01Mapper extends BaseMapper<OdsLwzxsfsjFeeStationEnter01>` → 继承 BaseMapper[OdsLwzxsfsjFeeStationEnter01]；
       Java 侧实现类由 MyBatis-Plus 动态代理生成，Python 侧直接实例化。
    2) `@Repository` → Spring 容器装配；Python 侧由 SpringUtils 注册（见 config 层），
       本类保留注解语义，无运行期副作用。
    3) `List<T>` → `list[T]`；`String` → `str`；`Long` → `int`。
    4) Mapper XML 与接口同名方法一一对应，方法名保持 Java 原样作为 statement id。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(OdsLwzxsfsjFeeStationEnter01)

    def selectOdsLwzxsfsjFeeStationEnter01ById(self, bigId: int) -> Optional[OdsLwzxsfsjFeeStationEnter01]:
        """查询收费站入口数据

        @param bigId 收费站入口数据ID
        @return 收费站入口数据

        【Java→Python】原方法由 Mapper XML 中的 <select> 实现；
        此处复用 BaseMapper 的内存查询，语义等价于 selectXxxById/selectXxxList。
        """
        return self.selectById(bigId)

    def selectOdsLwzxsfsjFeeStationEnter01List(self, odsLwzxsfsjFeeStationEnter01: OdsLwzxsfsjFeeStationEnter01) -> list[OdsLwzxsfsjFeeStationEnter01]:
        """查询收费站入口数据列表

        @param odsLwzxsfsjFeeStationEnter01 收费站入口数据
        @return 收费站入口数据集合

        【Java→Python】原方法由 Mapper XML 中的 <select> 实现；
        此处复用 BaseMapper 的内存查询，语义等价于 selectXxxById/selectXxxList。
        """
        return self.selectList(odsLwzxsfsjFeeStationEnter01)
