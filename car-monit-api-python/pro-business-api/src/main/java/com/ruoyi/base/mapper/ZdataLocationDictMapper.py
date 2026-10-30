# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.ZdataLocationDictMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/ZdataLocationDictMapper.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.ZdataLocationDict import ZdataLocationDict

__all__ = ["ZdataLocationDictMapper"]


class ZdataLocationDictMapper(BaseMapper[ZdataLocationDict]):
    """车辆位置Mapper接口

    【Java→Python】
    1) `public interface ZdataLocationDictMapper extends BaseMapper<ZdataLocationDict>` → 继承 BaseMapper[ZdataLocationDict]；
       Java 侧实现类由 MyBatis-Plus 动态代理生成，Python 侧直接实例化。
    2) `@Repository` → Spring 容器装配；Python 侧由 SpringUtils 注册（见 config 层），
       本类保留注解语义，无运行期副作用。
    3) `List<T>` → `list[T]`；`String` → `str`；`Long` → `int`。
    4) Mapper XML 与接口同名方法一一对应，方法名保持 Java 原样作为 statement id。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(ZdataLocationDict)

    def selectZdataLocationDictById(self, id: int) -> Optional[ZdataLocationDict]:
        """查询车辆位置

        @param id 车辆位置ID
        @return 车辆位置

        【Java→Python】原方法由 Mapper XML 中的 <select> 实现；
        此处复用 BaseMapper 的内存查询，语义等价于 selectXxxById/selectXxxList。
        """
        return self.selectById(id)

    def selectZdataLocationDictList(self, zdataLocationDict: ZdataLocationDict) -> list[ZdataLocationDict]:
        """查询车辆位置列表

        @param zdataLocationDict 车辆位置
        @return 车辆位置集合

        【Java→Python】原方法由 Mapper XML 中的 <select> 实现；
        此处复用 BaseMapper 的内存查询，语义等价于 selectXxxById/selectXxxList。
        """
        return self.selectList(zdataLocationDict)
