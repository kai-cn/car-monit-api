# -*- coding: utf-8 -*-
"""``@Service`` Bean 生命周期启动器（P0-3，docs/迁移审阅报告.md B3）。

背景
----
Java 的 Spring 容器会构造**全部** ``@Service`` Bean 并执行 ``@PostConstruct``。
Python 侧没有容器：24 个 Controller（及其构造链）与 6 个 ``@Scheduled`` Bean
已由 ``app.routes`` / ``app.scheduler`` 覆盖，但以下 ``@Service`` + ``@PostConstruct``
的 Bean 在此前**从未被构造**（全工程检索仅 ``_smoke_*.py`` 引用）：

    SnapshotFlowSyncService    全量/增量同步线程（Java 启动即跑，报告 B3）
    KafkaProducerService       失败消息重试线程（Java 启动即跑，报告 B3）
    ElasticsearchQueryService  ES 客户端初始化（构造即建客户端对象）

为什么默认关闭（重要，不要随手改成默认开启）
--------------------------------------------
1. TODO(V2/决策②)：``SnapshotFlowSyncService.init`` 默认提交**300G 全量同步**
   （``sync.full-sync-enabled`` 的 Java 默认值是 true）——是否启用属
   docs/迁移审阅报告.md §6.2 D3 待业主拍板项，本模块不得替业务做决定。
2. TODO(V2/决策③)：多实例部署下这些后台线程会**重复执行**（无分布式锁），
   属报告 §6.2 D4 待拍板项。
3. shim 模式下启用会**污染数据**：Kafka 重试线程假发送成功后，会把失败记录
   在真实数据库里标记为"已发送"（P0-2 只在 prod 模式拒绝假发送）。

启用方式
--------
    APP_BEANS_ENABLED=true    （显式开启；建议仅在 CAR_MONIT_RUNTIME=prod 下使用）

已知差异（与 Java 的单例容器相比）
----------------------------------
``KafkaProducerService`` 构造时会自带一套 DataReliability / LossDetection /
DelayMonitoring 服务实例，而 ``@Scheduled`` 的 6 个 Bean 由 ``app.scheduler``
另行构造——两处实例互不共享（Java 是单例）。``@Scheduled`` 方法只挂在
scheduler 的实例上、发送回调只挂在本模块的实例上，行为不交叉；实例合并
属于 DI 收敛（报告 P1-6）的后续工作。
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Optional, Sequence

__all__ = ["BEAN_CLASSES", "beans_enabled", "start_beans", "shutdown_beans",
           "is_started", "started_beans"]

log = logging.getLogger(__name__)

_TRUTHY = {"1", "true", "yes", "on"}


def _load_bean_classes() -> tuple:
    """等价 Spring 组件扫描的结果（懒加载，避免 app.beans 早于 bootstrap 导入）。"""
    from com.ruoyi.base.service.impl.SnapshotFlowSyncService import SnapshotFlowSyncService
    from com.ruoyi.base.service.impl.KafkaProducerService import KafkaProducerService
    from com.ruoyi.base.service.optimization.ElasticsearchQueryService import (
        ElasticsearchQueryService,
    )

    return (SnapshotFlowSyncService, KafkaProducerService, ElasticsearchQueryService)


#: 组件扫描结果（懒加载属性的常量形态；测试通过 start_beans(bean_classes) 注入替身）
BEAN_CLASSES: Any = None


def beans_enabled() -> bool:
    """``APP_BEANS_ENABLED`` 是否显式开启（默认 False，见模块说明）。"""
    return (os.environ.get("APP_BEANS_ENABLED") or "").strip().lower() in _TRUTHY


class _BeanState:
    def __init__(self) -> None:
        self.instances: list[Any] = []
        self.names: list[str] = []
        self.lock = threading.Lock()


_STATE = _BeanState()


def start_beans(bean_classes: Optional[Sequence[type]] = None) -> str:
    """构造并初始化 Bean（等价容器 refresh 时的 Bean 实例化 + ``@PostConstruct``）。

    幂等：重复调用返回同一结果。默认仅当 ``APP_BEANS_ENABLED=true`` 才真正
    启动；``bean_classes`` 参数供测试注入替身（此时同样受开关控制，测试里
    需先设置环境变量）。
    """
    with _STATE.lock:
        if _STATE.instances:
            return _summary()
        if not beans_enabled():
            note = ("disabled (APP_BEANS_ENABLED not set; "
                    "见 app/beans.py 模块说明——TODO 决策②全量同步 / 决策③多实例)")
            log.info("[Bean生命周期] %s", note)
            return note

        from app.runtime import runtime_mode

        if runtime_mode() != "prod":
            log.warning("[Bean生命周期] APP_BEANS_ENABLED=true 但运行在 shim 模式："
                        "Kafka 假发送可能把真实库里的失败记录标成已发送（数据污染），"
                        "仅限无副作用的测试环境使用！")

        classes = tuple(bean_classes) if bean_classes is not None else _load_bean_classes()
        for bean_class in classes:
            # 构造即执行 @PostConstruct（移植约定：__init__ 末尾显式调用 init()）
            _STATE.instances.append(bean_class())
            _STATE.names.append(bean_class.__name__)
        note = _summary()
        log.info("[Bean生命周期] 已启动 %s（Java 侧 @Service + @PostConstruct 等价物）",
                 note)
        return note


def shutdown_beans() -> None:
    """调用各 Bean 的 ``destroy()``（``@PreDestroy`` 等价物），并清空注册表。"""
    with _STATE.lock:
        instances, _STATE.instances = _STATE.instances, []
        _STATE.names = []
    for bean in instances:
        destroy = getattr(bean, "destroy", None)
        if callable(destroy):
            try:
                destroy()
            except Exception:  # noqa: BLE001 - 与 Spring destroy 回调一致：尽力而为
                log.exception("[Bean生命周期] %s.destroy() 失败", type(bean).__name__)


def is_started() -> bool:
    return bool(_STATE.instances)


def started_beans() -> list[str]:
    return list(_STATE.names)


def _summary() -> str:
    if not _STATE.instances:
        return "disabled"
    return "%d bean(s): %s" % (len(_STATE.names), ", ".join(_STATE.names))
