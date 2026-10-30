# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.OdsSzdnGantryIpServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/OdsSzdnGantryIpServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.OdsSzdnGantry import OdsSzdnGantry
from com.ruoyi.base.domain.OdsSzdnGantryIp import OdsSzdnGantryIp
from com.ruoyi.base.mapper.OdsSzdnGantryIpMapper import OdsSzdnGantryIpMapper
from com.ruoyi.base.service.IOdsSzdnGantryIpService import IOdsSzdnGantryIpService
from com.ruoyi.base.service.IOdsSzdnGantryService import IOdsSzdnGantryService
from com.ruoyi.base.service.impl.OdsSzdnGantryServiceImpl import OdsSzdnGantryServiceImpl
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["OdsSzdnGantryIpServiceImpl"]


def _javaPlusEmpty(value: Any) -> str:
    """模拟 Java 的 `"" + value`（字符串拼接的隐式 toString）。

    【Java→Python】这是本文件最需要小心的差异：
    - Java：`"" + null` 结果是 **字符串 "null"**（不抛异常）；`"" + 123L` → "123"。
    - Python：`"" + None` 抛 TypeError；`"" + 123` 抛 TypeError（不做隐式转换）。
    因此这里显式还原：None → "null"，其余 → str(value)。
    注意随后 `CommonUtil.isNull(...)` 对 "null" 不做特殊处理，最终 key 会含 "null" 字样 ——
    与原 Java 行为完全一致（要改需改业务逻辑，不属于本次重构范围）。
    """
    if value is None:
        return "null"
    return str(value)


class OdsSzdnGantryIpServiceImpl(
        ServiceImpl[OdsSzdnGantryIpMapper, OdsSzdnGantryIp],
        IOdsSzdnGantryIpService):
    """省界设备ipService业务层处理

    【Java→Python】
    1) `@Autowired private IOdsSzdnGantryService odsSzdnGantryService;` → 构造注入接口，
       缺省 new `OdsSzdnGantryServiceImpl`（**生产装配需显式传入共享实例**，否则门架字典为空）。
    2) `selectOdsSzdnGantryIpMap()` 对每条记录写 10 个 key（4 组前缀 × (id|gantryCode)
       + 2 个裸编码），其中 id 是 `Long`，Java 写的是 `"" + rtn.getId()`
       → Python 必须用 `_javaPlusEmpty` 还原，否则 `"" + None`/`"" + int` 会直接抛 TypeError。
    3) `selectIPSet()` 直接透传 Mapper 的 `Set<String>`。
    """

    def __init__(self,
                 odsSzdnGantryIpMapper: Optional[OdsSzdnGantryIpMapper] = None,
                 odsSzdnGantryService: Optional[IOdsSzdnGantryService] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.odsSzdnGantryIpMapper = odsSzdnGantryIpMapper or OdsSzdnGantryIpMapper()
        self.odsSzdnGantryService = odsSzdnGantryService or OdsSzdnGantryServiceImpl()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.odsSzdnGantryIpMapper)

    def selectOdsSzdnGantryIpById(self, id: int) -> Optional[OdsSzdnGantryIp]:
        """查询省界设备ip

        :param id: 省界设备ipID
        :return: 省界设备ip
        """
        return self.odsSzdnGantryIpMapper.selectOdsSzdnGantryIpById(id)

    def selectOdsSzdnGantryIpList(self, odsSzdnGantryIp: OdsSzdnGantryIp) -> list[OdsSzdnGantryIp]:
        """查询省界设备ip列表

        :param odsSzdnGantryIp: 省界设备ip
        :return: 省界设备ip
        """
        return self.odsSzdnGantryIpMapper.selectOdsSzdnGantryIpList(odsSzdnGantryIp)

    def selectOdsSzdnGantryIpMap(self) -> dict[str, OdsSzdnGantryIp]:
        """查询省界设备ip列表（实际返回“10 种 key → 实体”大字典）

        :return: 省界设备ip集合

        【Java→Python】`"" + rtn.getId()`（Long）与 `"" + rtn.getGantryCode()`（String）
        统一走 `_javaPlusEmpty`，保证 null → "null"、数字 → 字符串，
        与 Java 的字符串拼接语义逐字一致；随后再交给 `CommonUtil.isNull` 做 trim。
        """
        map_: dict[str, OdsSzdnGantryIp] = {}
        list_ = self.getRedisList()

        for rtn in list_:

            # 门架
            map_["gantryip:" + CommonUtil.isNull(_javaPlusEmpty(rtn.id))] = rtn
            map_["gantryip:" + CommonUtil.isNull(_javaPlusEmpty(rtn.gantry_code))] = rtn

            # 省界门架称重事件
            map_["bwlocation:" + CommonUtil.isNull(_javaPlusEmpty(rtn.id))] = rtn
            map_["bwlocation:" + CommonUtil.isNull(_javaPlusEmpty(rtn.gantry_code))] = rtn

            # 省界门架抓拍事件模型
            map_["gantryid:" + CommonUtil.isNull(_javaPlusEmpty(rtn.id))] = rtn
            map_["gantryid:" + CommonUtil.isNull(_javaPlusEmpty(rtn.gantry_code))] = rtn

            # 卡口流水
            map_["gantry:" + CommonUtil.isNull(_javaPlusEmpty(rtn.id))] = rtn
            map_["gantry:" + CommonUtil.isNull(_javaPlusEmpty(rtn.gantry_code))] = rtn

            # 通过IP 或者code查询
            map_[CommonUtil.isNull(_javaPlusEmpty(rtn.id))] = rtn
            map_[CommonUtil.isNull(_javaPlusEmpty(rtn.gantry_code))] = rtn

        return map_

    def selectIPSet(self) -> set[str]:
        """设备 IP 集合（直接透传 Mapper）

        :return: 去重后的 IP 集合

        【Java→Python】Java `Set<String>` → Python `set[str]`，空结果为空集合而非 None。
        """
        return self.odsSzdnGantryIpMapper.selectIPSet()

    def updateRedis(self) -> list[OdsSzdnGantryIp]:
        """跟新redis（原注释即为此，含错别字，保留）

        :return: 省界设备ip列表（已回填 `odsSzdnGantry` 关联对象）

        【Java→Python】
        1) Java 里 `Map<String, OdsSzdnGantryIp> map = new HashMap<>();` 声明后**从未使用**
           （变量 `map` 是死代码），Python 侧不保留该无效变量，但在此注明以便逐行对照。
        2) 按 `gantryCode` 从门架字典回填 `odsSzdnGantry`（`exist = False` 字段）。
        """
        list_ = self.odsSzdnGantryIpMapper.selectOdsSzdnGantryIpList(OdsSzdnGantryIp())
        odsSzdnGantry = OdsSzdnGantry()
        osSzdnGantryMap: dict[str, OdsSzdnGantry] = self.odsSzdnGantryService.selectOdsSzdnGantryMap(odsSzdnGantry)
        for rtn in list_:
            key = CommonUtil.isNull(rtn.gantry_code)  # 门架编号
            if key in osSzdnGantryMap:
                rtn.ods_szdn_gantry = osSzdnGantryMap[key]
        self.redisCache.setCacheObject(Constants.gantry_ip, list_)
        return list_

    def getRedisList(self) -> list[OdsSzdnGantryIp]:
        """从缓存拿到carlist（原注释如此，实际取省界设备ip列表）

        :return: 省界设备ip列表

        【Java→Python】`(List) obj` 裸强转 → 直接赋值。
        """
        list_: Optional[list[OdsSzdnGantryIp]] = None
        obj: Any = self.redisCache.getCacheObject(Constants.gantry_ip)
        if obj is not None:
            list_ = obj
        else:
            list_ = self.updateRedis()
        return list_
