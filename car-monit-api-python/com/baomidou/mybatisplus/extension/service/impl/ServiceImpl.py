# -*- coding: utf-8 -*-
"""com.baomidou.mybatisplus.extension.service.impl.ServiceImpl

【无 Java 源文件：框架类替身】
Java 侧来自 MyBatis-Plus jar：com.baomidou.mybatisplus.extension.service.impl.ServiceImpl<M extends BaseMapper<T>, T>
按原包路径重建，使 Service 实现类的 extends 与 Java 完全一致：

    Java : public class XxxServiceImpl extends ServiceImpl<XxxMapper, Xxx> implements IXxxService
    Py   : class XxxServiceImpl(ServiceImpl[XxxMapper, Xxx], IXxxService)

【Java→Python 关键差异】
1) Java 的 ServiceImpl<M, T> 靠 Spring 把 Mapper 注入到 `baseMapper` 字段；
   Python 没有 DI 容器，改为**构造器参数**：
       super().__init__(XxxMapper())
   未传时默认 new 一个 Mapper（等价 Spring 的单例 Bean，但每个 ServiceImpl 各持一个实例，
   若要共享同一份「表数据」，需显式把同一个 Mapper 实例传进来——见各实现类的注释）。
2) 通用 CRUD 方法（save/getById/list/updateById/removeById...）由父类 IService 提供，
   子类只需实现业务接口声明的抽象方法。
3) Java 的 `@Transactional` 由 Spring AOP 代理实现；Python 侧无等价物，
   需要事务时显式使用 `with self.transaction():`（本替身仅提供占位，不做真实回滚）。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generic, Optional, TypeVar

from com.baomidou.mybatisplus.core.mapper.BaseMapper import BaseMapper
from com.baomidou.mybatisplus.extension.service.IService import IService

M = TypeVar("M", bound=BaseMapper)
T = TypeVar("T")

__all__ = ["ServiceImpl"]


class ServiceImpl(IService[T], Generic[M, T]):
    """MyBatis-Plus ServiceImpl<M, T> 的 Python 等价物。"""

    def __init__(self, mapper: Optional[M] = None) -> None:
        # 【Java→Python】Spring @Autowired 字段注入 → Python 构造器注入
        self.baseMapper = mapper

    @contextmanager
    def transaction(self):
        """`@Transactional` 的占位实现。

        【Java→Python】Java 由 Spring 事务管理器在方法前后开启/提交/回滚；
        内存表实现没有真正的回滚能力，这里只提供一个语义化的上下文，
        便于将来接入真实数据库事务（如 sqlalchemy 的 session.begin()）。
        """
        yield self
