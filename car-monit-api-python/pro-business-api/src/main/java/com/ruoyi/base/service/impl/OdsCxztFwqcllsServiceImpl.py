# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsCxztFwqcllsServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsCxztFwqcllsServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsCxztFwqclls import OdsCxztFwqclls
from com.ruoyi.base.mapper.OdsCxztFwqcllsMapper import OdsCxztFwqcllsMapper
from com.ruoyi.base.service.IOdsCxztFwqcllsService import IOdsCxztFwqcllsService
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsCxztFwqcllsServiceImpl"]


class OdsCxztFwqcllsServiceImpl(ServiceImpl[OdsCxztFwqcllsMapper, OdsCxztFwqclls], IOdsCxztFwqcllsService):
    """服务区车辆流水Service业务层处理

    【Java→Python】
    1) `@Autowired RedisCache` → 构造器注入（默认共享进程级内存 template）。
    2) 本类的 `selectOdsCxztFwqcllsByQueryUuids` 是典型的**逐 key 缓存 + 空值占位**实现：
       缓存未命中则查库，查到写缓存；**查不到也写缓存**（写入一个只带 datauuid 的空对象），
       用于阻挡后续重复穿透。Python 侧逐行还原，包括这个“伪空值占位”行为。
    """

    def __init__(self,
                 odsCxztFwqcllsMapper: Optional[OdsCxztFwqcllsMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsCxztFwqcllsMapper = odsCxztFwqcllsMapper or OdsCxztFwqcllsMapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsCxztFwqcllsMapper)

    def selectOdsCxztFwqcllsById(self, bigId: int) -> Optional[OdsCxztFwqclls]:
        """查询服务区车辆流水

        :param bigId: 服务区车辆流水ID
        :return: 服务区车辆流水

        【Java→Python】Java `Long bigId` → Python `int`；返回 None 对应 null。
        """
        return self.odsCxztFwqcllsMapper.selectOdsCxztFwqcllsById(bigId)

    def selectOdsCxztFwqcllsList(self, odsCxztFwqclls: OdsCxztFwqclls) -> list[OdsCxztFwqclls]:
        """查询服务区车辆流水列表

        :param odsCxztFwqclls: 服务区车辆流水
        :return: 服务区车辆流水
        """
        return self.odsCxztFwqcllsMapper.selectOdsCxztFwqcllsList(odsCxztFwqclls)

    def selectOdsCxztFwqcllsByQueryUuids(self, queryUuids: str) -> dict[str, OdsCxztFwqclls]:
        """按逗号分隔的 uuid 串批量取服务区车辆流水（带 Redis 缓存）

        :param queryUuids: 逗号分隔的 datauuid 串
        :return: uuid → 实体（缓存/库中不存在的 uuid **不会**出现在结果里）

        【Java→Python】
        1) `Arrays.stream(queryUuids.split(",")).collect(Collectors.toList())`
           → Python 直接 `queryUuids.split(",")` 就是 list[str]。
           细微差异：Java 的 `String.split` 会丢弃**末尾**空串（"a,b," → ["a","b"]），
           Python 的 `str.split` 会保留（→ ["a","b",""]）；由于下方 `isNotBlank(uuid)`
           会过滤空串，两者最终行为完全一致。
        2) `Object obj` + `(OdsCxztFwqclls) obj` 强转 → Python 无强制转换，
           取到的就是 `_ValueOperations.get` 返回的 `deepcopy` 副本（模拟 Redis 序列化隔离）。
        3) 未命中且库中无数据时写入 `querybo`（只设置了 datauuid 的空对象）作为占位，
           下次命中该 key 时 `obj is not None` 成立，但**不会** put 进返回 map —— 保持原逻辑。
        """
        map_: dict[str, OdsCxztFwqclls] = {}
        if CommonUtil.isNotBlank(queryUuids):
            uuidList = queryUuids.split(",")
            for uuid in uuidList:
                if CommonUtil.isNotBlank(uuid):
                    # redis查找
                    key = Constants.DATE_SERVICE_AREA_CAPTURE + uuid
                    obj: Any = self.redisCache.getCacheObject(key)
                    if obj is not None:
                        map_[uuid] = obj
                    else:
                        querybo = OdsCxztFwqclls()
                        querybo.datauuid = uuid
                        list_ = self.odsCxztFwqcllsMapper.selectOdsCxztFwqcllsList(querybo)
                        if list_ is not None and len(list_) > 0:
                            map_[uuid] = list_[0]
                            self.redisCache.setCacheObject(key, list_[0])
                        else:
                            self.redisCache.setCacheObject(key, querybo)
        return map_
