# -*- coding: utf-8 -*-
"""com.ruoyi.base.mapper.OdsSzdnProvinceBorderVehicleWeightNewstructureMapper

源文件：pro-business-api/src/main/java/com/ruoyi/base/mapper/OdsSzdnProvinceBorderVehicleWeightNewstructureMapper.java
"""
from __future__ import annotations

from typing import Optional

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure import OdsSzdnProvinceBorderVehicleWeightNewstructure

__all__ = ["OdsSzdnProvinceBorderVehicleWeightNewstructureMapper"]


class OdsSzdnProvinceBorderVehicleWeightNewstructureMapper(BaseMapper[OdsSzdnProvinceBorderVehicleWeightNewstructure]):
    """省界称重Mapper接口

    【Java→Python】
    1) `interface ... extends BaseMapper<...>` → 继承同名泛型基类（类名较长，属正常）。
    2) 主键是业务 UUID `datauuid`（@TableId）；但 Java 接口把查询参数命名为 `dataSource`
       （生成器生成的方法签名如此），实际传入的是主键值 `datauuid`。
    3) `ByUuidList` 用 `datauuid IN (...)`，与主键一致，但仍按「UUID 列表」语义实现，
       以免与 selectBatchIds 的语义差异混淆。
    """

    def __init__(self) -> None:
        # 【Java→Python】MyBatis-Plus 通过接口泛型反射得到实体类型；Python 显式传入
        super().__init__(OdsSzdnProvinceBorderVehicleWeightNewstructure)

    def selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(self, dataSource: str) -> Optional[OdsSzdnProvinceBorderVehicleWeightNewstructure]:
        """查询省界称重

        :param dataSource: 省界称重ID（Java 注释如此，实为 datauuid）
        :return: 省界称重

        【Java→Python】复用 BaseMapper 主键查询（@TableId = datauuid）。
        """
        return self.selectById(dataSource)

    def selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(self, odsSzdnProvinceBorderVehicleWeightNewstructure: OdsSzdnProvinceBorderVehicleWeightNewstructure) -> list[OdsSzdnProvinceBorderVehicleWeightNewstructure]:
        """查询省界称重列表

        :param odsSzdnProvinceBorderVehicleWeightNewstructure: 省界称重
        :return: 省界称重集合

        【Java→Python】非空字段等值过滤，等价 XML 的 `<if test="xxx != null">`。
        """
        return self.selectList(odsSzdnProvinceBorderVehicleWeightNewstructure)

    def selectOdsSzdnProvinceBorderVehicleWeightNewstructureByUuidList(self, uuidList: list[str]) -> list[OdsSzdnProvinceBorderVehicleWeightNewstructure]:
        """查询省界称重 : 通过IDS查询

        :param uuidList: 业务 UUID（datauuid）集合
        :return: 匹配的省界称重记录

        【Java→Python】对应 SQL：
            SELECT * FROM ods_szdn_province_border_vehicle_weight_newstructure
             WHERE datauuid IN (#{uuidList})
        Java 用 `<foreach>` 展开 IN；Python 用集合成员判断，空列表直接返回空结果。
        """
        if not uuidList:
            return []
        wanted = set(uuidList)
        return self.selectWhere(lambda r: r.datauuid in wanted)
