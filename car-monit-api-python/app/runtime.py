# -*- coding: utf-8 -*-
"""运行时模式开关（P0-2，docs/迁移审阅报告.md B2）。

背景
----
Kafka / Pulsar / RocketMQ / ES / Redis 写 / JdbcTemplate / Forest 的进程内替身在
"发送/写入"时**假装成功** —— 数据不会离开本进程。开发/测试（shim 模式）这是特性；
生产（prod 模式）这是事故：消息显示"已发送"但 broker 上没有、缓存显示"已写入"
但其他实例读不到、ES 导出显示成功但文件里没有集群数据。

用法
----
    CAR_MONIT_RUNTIME=shim（默认）  开发/测试：替身维持现状
    CAR_MONIT_RUNTIME=prod          生产：所有"假成功"操作抛 :class:`ShimOperationError`

与 Java 行为等价性的说明
------------------------
prod 模式下抛错**不是新增差异**，而是把"静默丢数据"还原成"与 Java 中间件宕机
一致的失败路径"：Kafka 发送抛 KafkaException、ES 查询抛 IOException 后
``UnifiedQueryService`` 走 MySQL 降级、``EsIndexManageService.init`` 的
catch 分支照常吞错启动 —— 这些 catch 已在移植时逐行镜像（对照
EsIndexManageService.java:116-134）。真实客户端适配器（P2-2/P2-3）落地后，
prod 模式的这些入口改接真实实现，业务代码无需再改。
"""
from __future__ import annotations

import os

__all__ = ["RUNTIME_ENV", "ShimOperationError", "runtime_mode", "is_strict",
           "reject_shim_operation", "startup_fail_fast"]

#: 环境变量名（Python 宿主层新增，与 CAR_MONIT_* 系列同族，见 README_PY）
RUNTIME_ENV = "CAR_MONIT_RUNTIME"

#: 启动期 fail-fast 开关（P0-5）：默认开启，'false'/'0'/'no'/'off' 关闭
FAIL_FAST_ENV = "CAR_MONIT_STARTUP_FAIL_FAST"

#: prod 的别名（宽松解析，避免拼写踩坑）
_STRICT_ALIASES = {"prod", "production", "strict"}


class ShimOperationError(RuntimeError):
    """替身在 prod 模式下拒绝执行"假成功"操作。"""


def runtime_mode() -> str:
    """当前运行时模式：``'shim'``（默认）或 ``'prod'``。

    每次调用即时读环境变量，不做进程级缓存（便于测试用 monkeypatch 切换）。
    """
    value = (os.environ.get(RUNTIME_ENV) or "").strip().lower()
    return "prod" if value in _STRICT_ALIASES else "shim"


def is_strict() -> bool:
    """是否运行在 prod（严格）模式。"""
    return runtime_mode() == "prod"


def startup_fail_fast() -> bool:
    """启动期 fail-fast 开关（P0-5，报告 B5）。

    Spring 的行为是容器 refresh 失败即退出；此前 Python 侧对 Controller 缺失、
    Mapper 安装失败、statement 缺失都只记日志继续跑。默认恢复 Spring 语义
    （失败即抛错退出）；显式 ``CAR_MONIT_STARTUP_FAIL_FAST=false`` 可退回旧行为
    （仅日志，供应急排障）。
    """
    value = (os.environ.get(FAIL_FAST_ENV) or "").strip().lower()
    return value not in {"false", "0", "no", "off"}


def reject_shim_operation(operation: str, remedy: str = "") -> None:
    """prod 模式下拒绝替身的"假成功"操作；shim 模式下是空操作。

    :param operation: 操作名（如 ``KafkaTemplate.send``），用于报错定位
    :param remedy: 补救说明（接哪个真实适配器 / 对应报告条目）
    """
    if not is_strict():
        return
    message = (
        "[%s] 在 CAR_MONIT_RUNTIME=prod 下被拒绝：该替身操作只会写入本进程内存、"
        "外部系统不会收到任何数据（假成功）。" % operation)
    if remedy:
        message += remedy
    message += (" 请接入真实中间件适配器（docs/迁移审阅报告.md P0-2 与 P2-2/P2-3），"
                "或仅在开发/测试环境使用 CAR_MONIT_RUNTIME=shim。")
    raise ShimOperationError(message)
