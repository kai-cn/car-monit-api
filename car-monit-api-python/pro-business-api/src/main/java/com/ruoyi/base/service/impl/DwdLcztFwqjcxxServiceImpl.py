# -*- coding: utf-8 -*-
"""com.ruoyi.base.service.impl.DwdLcztFwqjcxxServiceImpl

源文件：pro-business-api/src/main/java/com/ruoyi/base/service/impl/DwdLcztFwqjcxxServiceImpl.java
"""
from __future__ import annotations

from typing import Any, Optional

import com.ruoyi.common.utils.CommonUtil as CommonUtil
from com.baomidou.mybatisplus.extension.service.impl.ServiceImpl import ServiceImpl
from com.ruoyi.base.domain.DwdLcztFwqjcxx import DwdLcztFwqjcxx
from com.ruoyi.base.mapper.DwdLcztFwqjcxxMapper import DwdLcztFwqjcxxMapper
from com.ruoyi.base.service.IDwdLcztFwqjcxxService import IDwdLcztFwqjcxxService
from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.redis.RedisCache import RedisCache

__all__ = ["DwdLcztFwqjcxxServiceImpl"]


class DwdLcztFwqjcxxServiceImpl(ServiceImpl[DwdLcztFwqjcxxMapper, DwdLcztFwqjcxx], IDwdLcztFwqjcxxService):
    """服务区基础信息Service业务层处理

    【Java→Python】
    1) `@Autowired private RedisCache redisCache;` → 构造器注入；RedisCache 默认共享进程级
       内存 template（见 RedisCache 模块注释），等价于 Spring 的单例 Bean。
    2) Java 的 `agentPk` 是 `String` 主键，Python 侧同名字段 `agent_pk`（见 domain）。
    3) Java 方法名 `selectXxxById(String agentPk)` 的第一参数语义是**主键**，
       这里保持方法名与参数名完全一致，不额外包装。
    """

    def __init__(self,
                 dwdLcztFwqjcxxMapper: Optional[DwdLcztFwqjcxxMapper] = None,
                 redisCache: Optional[RedisCache] = None) -> None:
        self.dwdLcztFwqjcxxMapper = dwdLcztFwqjcxxMapper or DwdLcztFwqjcxxMapper()
        self.redisCache = redisCache or RedisCache()
        super().__init__(self.dwdLcztFwqjcxxMapper)

    def selectDwdLcztFwqjcxxById(self, agentPk: str) -> Optional[DwdLcztFwqjcxx]:
        """查询服务区基础信息

        :param agentPk: 服务区基础信息ID
        :return: 服务区基础信息

        【Java→Python】返回 None 对应 Java 的 null。
        """
        return self.dwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxById(agentPk)

    def selectDwdLcztFwqjcxxList(self, dwdLcztFwqjcxx: DwdLcztFwqjcxx) -> list[DwdLcztFwqjcxx]:
        """查询服务区基础信息列表

        :param dwdLcztFwqjcxx: 服务区基础信息
        :return: 服务区基础信息

        【Java→Python】`List<T>` → `list[T]`。
        """
        return self.dwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxList(dwdLcztFwqjcxx)

    def updateRedis(self) -> list[DwdLcztFwqjcxx]:
        """跟新redis（原注释即为此，含错别字，保留）

        【Java→Python】`new DwdLcztFwqjcxx()` 作为查询条件 = 全字段为 null = 查全表（WHERE 1=1）。
        """
        list_ = self.dwdLcztFwqjcxxMapper.selectDwdLcztFwqjcxxList(DwdLcztFwqjcxx())
        self.redisCache.setCacheObject(Constants.fwq_name, list_)
        return list_

    def getServiceNameMap(self) -> dict[str, DwdLcztFwqjcxx]:
        """服务区名称 → 服务区实体 的映射（首次访问时回填缓存）

        【Java→Python】
        1) `Object obj = redisCache.getCacheObject(...)` 是 `Object` 类型，Java 用裸 `(List)` 强转，
           运行时无泛型校验（unchecked warning）。Python 无强制转换，直接使用；若缓存中存的
           不是 list，Java 会在 for 循环处抛 ClassCastException，Python 则在迭代处抛 TypeError，
           失败点一致。
        2) `map.put(CommonUtil.isNull(x), x)`：key 为 `null → ""` 的字符串，
           因此多条 `fwqmc` 为空的数据会互相覆盖，只保留最后一条 —— 原实现如此，未做修正。
        """
        list_: Optional[list[DwdLcztFwqjcxx]] = None
        obj: Any = self.redisCache.getCacheObject(Constants.fwq_name)
        if obj is not None:
            list_ = obj
        else:
            list_ = self.updateRedis()

        map_: dict[str, DwdLcztFwqjcxx] = {}
        for fwqjcxx in list_:
            map_[CommonUtil.isNull(fwqjcxx.fwqmc)] = fwqjcxx
        return map_
