# -*- coding: utf-8 -*-
"""com.baomidou.mybatisplus.extension.service.IService

【无 Java 源文件：框架类替身】
Java 侧来自 MyBatis-Plus jar：com.baomidou.mybatisplus.extension.service.IService<T>
按原包路径重建，使 Service 接口的 import 与 Java 完全一致：

    Java : import com.baomidou.mybatisplus.extension.service.IService;
    Py   : from com.baomidou.mybatisplus.extension.service.IService import IService

【Java→Python 关键差异】
1) MyBatis-Plus 的 IService 是「Service 层通用 CRUD」接口，默认实现类为 ServiceImpl<M, T>
   （通过 Spring 注入 baseMapper）。Python 侧没有泛型反射，改为：
   - 实现类在构造时把 Mapper 实例赋给 `self.baseMapper`；
   - 本类用 `baseMapper` 委托实现通用 CRUD。
2) `boolean save(T)` → `bool`（内部 `mapper.insert(...) > 0`）。
3) `List<T> list(Wrapper<T> queryWrapper)` 在 Python 中方法名与内置 `list` 同名，
   类内部一律用 `builtins`/推导式避免歧义——这是 Java 与 Python 的一处显著差异。
4) `IPage<T> page(IPage<T> page, Wrapper<T>)` → Python 简化为 `page(pageNum, pageSize, query=None)`
   返回当前页数据列表（分页对象见 com.ruoyi.common.core.page.TableDataInfo）。
"""
from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper

T = TypeVar("T")

__all__ = ["IService"]


class IService(Generic[T]):
    """MyBatis-Plus IService<T> 的 Python 等价物（通用 CRUD 门面）。"""

    # 【Java→Python】Java 由 Spring 注入 serviceImpl 的 baseMapper；
    # Python 由实现类构造函数显式赋值（约定见各 *ServiceImpl.__init__）。
    baseMapper: Optional[BaseMapper] = None

    # ------------------------------------------------------------------ 查询
    def getBaseMapper(self) -> BaseMapper:
        """等价 getBaseMapper()。"""
        if self.baseMapper is None:
            raise RuntimeError("baseMapper 未注入：请在 *ServiceImpl.__init__ 中赋值")
        return self.baseMapper

    def getById(self, id: Any) -> Optional[T]:
        """等价 getById(Serializable)。"""
        return self.getBaseMapper().selectById(id)

    def list(self, query: Any = None) -> List[T]:
        """等价 list(Wrapper<T>)：无条件时传 None。"""
        return self.getBaseMapper().selectList(query)

    def listByIds(self, id_list) -> List[T]:
        """等价 listByIds(Collection<? extends Serializable>)。"""
        return self.getBaseMapper().selectBatchIds(id_list)

    def getOne(self, query: Any = None) -> Optional[T]:
        """等价 getOne(Wrapper<T>, boolean throwEx=false)。"""
        return self.getBaseMapper().selectOne(query)

    def count(self, query: Any = None) -> int:
        """等价 count(Wrapper<T>)：Java 返回 long，Python 为 int。"""
        return self.getBaseMapper().selectCount(query)

    def page(self, page_num: int = 1, page_size: int = 10, query: Any = None) -> List[T]:
        """等价 page(IPage<T>, Wrapper<T>)。

        【Java→Python】Java 用 IPage 承载 total/records/current/size；
        Python 精简为「返回当前页记录」（total 可另行调用 count）。
        """
        rows = self.list(query)
        start = max(page_num - 1, 0) * max(page_size, 0)
        return rows[start:start + page_size]

    # ------------------------------------------------------------------ 写入
    def save(self, entity: T) -> bool:
        """等价 save(T)：影响行数 > 0 视为成功。"""
        return self.getBaseMapper().insert(entity) > 0

    def saveBatch(self, entity_list) -> bool:
        """等价 saveBatch(Collection<T>)：逐条 insert（无 JDBC batch 概念）。"""
        mapper = self.getBaseMapper()
        for entity in entity_list:
            mapper.insert(entity)
        return True

    def saveOrUpdate(self, entity: T) -> bool:
        """等价 saveOrUpdate(T)：主键存在则更新，否则插入。"""
        return self.getBaseMapper().insertOrUpdate(entity) > 0

    def updateById(self, entity: T) -> bool:
        """等价 updateById(T)：影响行数 > 0 视为成功。"""
        return self.getBaseMapper().updateById(entity) > 0

    def updateBatchById(self, entity_list) -> bool:
        """等价 updateBatchById(Collection<T>)：逐条 updateById。"""
        mapper = self.getBaseMapper()
        for entity in entity_list:
            mapper.updateById(entity)
        return True

    def removeById(self, id: Any) -> bool:
        """等价 removeById(Serializable)。"""
        return self.getBaseMapper().deleteById(id) > 0

    def removeByIds(self, id_list) -> bool:
        """等价 removeByIds(Collection<? extends Serializable>)。"""
        return self.getBaseMapper().deleteBatchIds(id_list) > 0
