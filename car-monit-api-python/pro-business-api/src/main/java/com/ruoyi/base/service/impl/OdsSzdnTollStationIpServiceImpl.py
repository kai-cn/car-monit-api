# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsSzdnTollStationIpServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsSzdnTollStationIpServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsSzdnToll import OdsSzdnToll
from com.ruoyi.base.domain.OdsSzdnTollStationIp import OdsSzdnTollStationIp
from com.ruoyi.base.mapper.OdsSzdnTollStationIpMapper import OdsSzdnTollStationIpMapper
from com.ruoyi.base.service.IOdsSzdnTollService import IOdsSzdnTollService
from com.ruoyi.base.service.IOdsSzdnTollStationIpService import IOdsSzdnTollStationIpService
from com.ruoyi.base.service.impl.OdsSzdnTollServiceImpl import OdsSzdnTollServiceImpl
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsSzdnTollStationIpServiceImpl"]


class OdsSzdnTollStationIpServiceImpl(
        ServiceImpl[OdsSzdnTollStationIpMapper, OdsSzdnTollStationIp],
        IOdsSzdnTollStationIpService):
    """收费站ipService业务层处理

    【Java→Python】
    1) `@Autowired private IOdsSzdnTollService odsSzdnTollService;` —— Java 注入的是**接口**。
       Python 无 DI 容器，构造参数按接口类型标注，缺省时 new 一个 `OdsSzdnTollServiceImpl`。
       **注意**：缺省实例会持有自己的 `OdsSzdnTollMapper`（空表），
       生产装配时必须显式传入与其它 Service 共享的同一个实例（模拟 Spring 单例）。
    2) `updateRedis()` 存在 N+1 式的关联：先查收费站字典，再逐条 `setOdsSzdnToll(...)`。
       关联字段 `odsSzdnToll` 是 `@TableField(exist = false)`，不落库，只用于出参拼装。
    3) `selectStationIpMap()` 对每条记录写入 8 个 key（4 组前缀 × ip/tollCode + 2 个裸编码
       + 1 个清洗后的收费站名），是“多路复用 Map”的写法，Python 逐行还原。
    """

    def __init__(self,
                 odsSzdnTollStationIpMapper: Optional[OdsSzdnTollStationIpMapper] = None,
                 odsSzdnTollService: Optional[IOdsSzdnTollService] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsSzdnTollStationIpMapper = odsSzdnTollStationIpMapper or OdsSzdnTollStationIpMapper()
        self.odsSzdnTollService = odsSzdnTollService or OdsSzdnTollServiceImpl()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsSzdnTollStationIpMapper)

    def selectOdsSzdnTollStationIpById(self, id: int) -> Optional[OdsSzdnTollStationIp]:
        """查询收费站ip

        :param id: 收费站ipID
        :return: 收费站ip

        【Java→Python】`Long id` → `int`。
        """
        return self.odsSzdnTollStationIpMapper.selectOdsSzdnTollStationIpById(id)

    def selectOdsSzdnTollStationIpList(
            self, odsSzdnTollStationIp: OdsSzdnTollStationIp) -> list[OdsSzdnTollStationIp]:
        """查询收费站ip列表

        :param odsSzdnTollStationIp: 收费站ip
        :return: 收费站ip
        """
        return self.odsSzdnTollStationIpMapper.selectOdsSzdnTollStationIpList(odsSzdnTollStationIp)

    def selectStationIpMap(self) -> dict[str, OdsSzdnTollStationIp]:
        """查询收费站ip列表（实际返回“多种前缀的 key → 实体”大字典）

        :return: 收费站ip集合

        【Java→Python】key 由字符串直接拼接（`"stationip:" + ...`），
        Python 的 `+` 拼接要求两边都是 str，而字段本身是 `str`，没有 Java 的隐式 toString 问题。
        若字段为 None，`CommonUtil.isNull` 先转成 ""，行为与 Java 一致。
        """
        map_: dict[str, OdsSzdnTollStationIp] = {}
        # 收费站ip列表
        list_ = self.getRedisList()
        for rtn in list_:
            map_["stationip:" + CommonUtil.isNull(rtn.ip)] = rtn
            map_["stationip:" + CommonUtil.isNull(rtn.toll_code)] = rtn

            map_["station:" + CommonUtil.isNull(rtn.ip)] = rtn
            map_["station:" + CommonUtil.isNull(rtn.toll_code)] = rtn

            # 根据code查询
            map_[CommonUtil.isNull(rtn.ip)] = rtn
            map_[CommonUtil.isNull(rtn.toll_code)] = rtn

            map_[CommonUtil.repalaceSzdnTollName(rtn.toll_name)] = rtn

        return map_

    def updateRedis(self) -> list[OdsSzdnTollStationIp]:
        """跟新redis（原注释即为此，含错别字，保留）

        :return: 收费站ip列表（已回填 `odsSzdnToll` 关联对象）

        【Java→Python】
        1) `new OdsSzdnTollStationIp()` 作为查询条件 = 全表查询。
        2) `odsSzdnTollService.selectOdsSzdnTollMap(new OdsSzdnToll())` 拿到“编码 → 收费站”字典，
           再按 `tollCode` 回填；`containsKey` + `get` 两步 → Python 用 `in` + 下标访问。
        3) `return  list;` 原文两个空格，属格式细节。
        """
        # 收费站ip列表
        list_ = self.odsSzdnTollStationIpMapper.selectOdsSzdnTollStationIpList(OdsSzdnTollStationIp())
        # 收费站map
        odsSzdnTollMap: dict[str, OdsSzdnToll] = self.odsSzdnTollService.selectOdsSzdnTollMap(OdsSzdnToll())
        for rtn in list_:
            key = CommonUtil.isNull(rtn.toll_code)  # 收费站编号
            if key in odsSzdnTollMap:
                rtn.ods_szdn_toll = odsSzdnTollMap[key]
        self.redisCache.setCacheObject(Constants.station_ip, list_)
        return list_

    def getRedisList(self) -> list[OdsSzdnTollStationIp]:
        """从缓存拿到redis（原注释如此，实际取收费站ip列表）

        :return: 收费站ip列表

        【Java→Python】`(List) obj` 裸强转 → 直接赋值（缓存里是 deepcopy 出来的新对象）。
        """
        list_: Optional[list[OdsSzdnTollStationIp]] = None
        obj: Any = self.redisCache.getCacheObject(Constants.station_ip)
        if obj is not None:
            list_ = obj
        else:
            list_ = self.updateRedis()
        return list_
