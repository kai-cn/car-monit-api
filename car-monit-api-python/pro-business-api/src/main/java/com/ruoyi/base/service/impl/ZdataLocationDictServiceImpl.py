# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.ZdataLocationDictServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/ZdataLocationDictServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.ZdataLocationDict import ZdataLocationDict
from com.ruoyi.base.mapper.ZdataLocationDictMapper import ZdataLocationDictMapper
from com.ruoyi.base.service.IZdataLocationDictService import IZdataLocationDictService
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["ZdataLocationDictServiceImpl"]


class ZdataLocationDictServiceImpl(ServiceImpl[ZdataLocationDictMapper, ZdataLocationDict], IZdataLocationDictService):
    """车辆位置Service业务层处理

    【Java→Python】
    1) 缓存 key 为 `Constants.dev_post`（全量车辆位置字典列表），
       与 `DwdLcztFwqjcxxServiceImpl` 的“整表缓存 + 首访回填”模式相同。
    2) Java 的 `getRawCode()` → Python 字段 `raw_code`（snake_case 映射规则见 domain 模块头注释）。
    """

    def __init__(self,
                 zdataLocationDictMapper: Optional[ZdataLocationDictMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.zdataLocationDictMapper = zdataLocationDictMapper or ZdataLocationDictMapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.zdataLocationDictMapper)

    def selectZdataLocationDictById(self, id: int) -> Optional[ZdataLocationDict]:
        """查询车辆位置

        :param id: 车辆位置ID
        :return: 车辆位置

        【Java→Python】`Long id` → `int`。
        """
        return self.zdataLocationDictMapper.selectZdataLocationDictById(id)

    def selectZdataLocationDictList(self, zdataLocationDict: ZdataLocationDict) -> list[ZdataLocationDict]:
        """查询车辆位置列表

        :param zdataLocationDict: 车辆位置
        :return: 车辆位置
        """
        return self.zdataLocationDictMapper.selectZdataLocationDictList(zdataLocationDict)

    def updateRedis(self) -> list[ZdataLocationDict]:
        """跟新redis（原注释即为此，含错别字，保留）

        【Java→Python】`new ZdataLocationDict()` = 无条件全表查询，见同包 `DwdLcztFwqjcxxServiceImpl`。
        """
        list_ = self.zdataLocationDictMapper.selectZdataLocationDictList(ZdataLocationDict())
        self.redisCache.setCacheObject(Constants.dev_post, list_)
        return list_

    def getRedisList(self) -> dict[str, ZdataLocationDict]:
        """从缓存拿到carlist

        【Java→Python】`(List) obj` 裸强转 → 直接赋值；
        key 用 `CommonUtil.isNull(rawCode)`，因此 rawCode 为 null 的记录会归到 "" 键并互相覆盖。
        """
        list_: Optional[list[ZdataLocationDict]] = None
        obj: Any = self.redisCache.getCacheObject(Constants.dev_post)
        if obj is not None:
            list_ = obj
        else:
            list_ = self.updateRedis()

        map_: dict[str, ZdataLocationDict] = {}
        for rtn in list_:
            map_[CommonUtil.isNull(rtn.raw_code)] = rtn
        return map_
