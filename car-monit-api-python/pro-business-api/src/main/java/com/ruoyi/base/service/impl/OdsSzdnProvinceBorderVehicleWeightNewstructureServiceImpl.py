# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure import (
    OdsSzdnProvinceBorderVehicleWeightNewstructure,
)
from com.ruoyi.base.mapper.OdsSzdnProvinceBorderVehicleWeightNewstructureMapper import (
    OdsSzdnProvinceBorderVehicleWeightNewstructureMapper,
)
from com.ruoyi.base.service.IOdsSzdnProvinceBorderVehicleWeightNewstructureService import (
    IOdsSzdnProvinceBorderVehicleWeightNewstructureService,
)
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl"]


class OdsSzdnProvinceBorderVehicleWeightNewstructureServiceImpl(
        ServiceImpl[OdsSzdnProvinceBorderVehicleWeightNewstructureMapper,
                   OdsSzdnProvinceBorderVehicleWeightNewstructure],
        IOdsSzdnProvinceBorderVehicleWeightNewstructureService):
    """省界称重Service业务层处理

    【Java→Python】
    1) 超长类名在 Python 中按括号续行拆分；`import` 同理用括号包起来，避免 E501 长行。
    2) `selectXxxById(String dataSource)` 的参数名 `dataSource` 是 RuoYi 代码生成器的产物
       （本表主键列名就叫 data_source），语义上仍是主键，Python 保持同名。
    3) 缓存 key：`Constants.DATE_BORDER_WEIGHING_CAPTURE + datauuid`，空值占位逻辑同
       `OdsCxztFwqcllsServiceImpl`。
    """

    def __init__(self,
                 odsSzdnProvinceBorderVehicleWeightNewstructureMapper:
                 Optional[OdsSzdnProvinceBorderVehicleWeightNewstructureMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsSzdnProvinceBorderVehicleWeightNewstructureMapper = (
            odsSzdnProvinceBorderVehicleWeightNewstructureMapper
            or OdsSzdnProvinceBorderVehicleWeightNewstructureMapper()
        )
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsSzdnProvinceBorderVehicleWeightNewstructureMapper)

    def selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(
            self, dataSource: str) -> Optional[OdsSzdnProvinceBorderVehicleWeightNewstructure]:
        """查询省界称重

        :param dataSource: 省界称重ID
        :return: 省界称重
        """
        return self.odsSzdnProvinceBorderVehicleWeightNewstructureMapper \
            .selectOdsSzdnProvinceBorderVehicleWeightNewstructureById(dataSource)

    def selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(
            self, odsSzdnProvinceBorderVehicleWeightNewstructure: OdsSzdnProvinceBorderVehicleWeightNewstructure
    ) -> list[OdsSzdnProvinceBorderVehicleWeightNewstructure]:
        """查询省界称重列表

        :param odsSzdnProvinceBorderVehicleWeightNewstructure: 省界称重
        :return: 省界称重
        """
        return self.odsSzdnProvinceBorderVehicleWeightNewstructureMapper \
            .selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(odsSzdnProvinceBorderVehicleWeightNewstructure)

    def selectOdsSzdnProvinceBorderVehicleWeightNewstructureByQueryUuids(
            self, queryUuids: str) -> dict[str, OdsSzdnProvinceBorderVehicleWeightNewstructure]:
        """查询省界称重 : 通过IDS查询

        :param queryUuids: 逗号分隔的 datauuid 串
        :return: datauuid → 实体

        【Java→Python】
        1) Javadoc 里只写了 `@return`，漏了 `@param queryUuids` —— 原样保留（不补注释）。
        2) `Arrays.stream(queryUuids.split(",")).collect(Collectors.toList())`
           → Python `split(",")`；空串过滤与 Java 一致。
        3) 未命中且查无数据 → `redisCache.setCacheObject(key, querybo)` 空对象占位，原样保留。
        """
        map_: dict[str, OdsSzdnProvinceBorderVehicleWeightNewstructure] = {}
        if CommonUtil.isNotBlank(queryUuids):
            uuidList = queryUuids.split(",")
            for uuid in uuidList:
                if CommonUtil.isNotBlank(uuid):
                    # redis查找
                    key = Constants.DATE_BORDER_WEIGHING_CAPTURE + uuid
                    obj: Any = self.redisCache.getCacheObject(key)
                    if obj is not None:
                        map_[uuid] = obj
                    else:
                        querybo = OdsSzdnProvinceBorderVehicleWeightNewstructure()
                        querybo.datauuid = uuid
                        list_ = self.odsSzdnProvinceBorderVehicleWeightNewstructureMapper \
                            .selectOdsSzdnProvinceBorderVehicleWeightNewstructureList(querybo)
                        if list_ is not None and len(list_) > 0:
                            map_[uuid] = list_[0]
                            self.redisCache.setCacheObject(key, list_[0])
                        else:
                            self.redisCache.setCacheObject(key, querybo)
        return map_
