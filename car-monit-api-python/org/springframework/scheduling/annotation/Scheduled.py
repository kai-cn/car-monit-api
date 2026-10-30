# -*- coding: utf-8 -*-
"""org.springframework.scheduling.annotation.Scheduled

【无 Java 源文件：框架类替身】
Java 侧来自 Spring Framework：`@Scheduled(fixedRate = 600000)`。
Spring 容器启动时由 `ScheduledAnnotationBeanPostProcessor` 扫描注解，并向
`TaskScheduler` 注册定时任务，**业务代码不需要自己起线程**。

【Java→Python 关键差异】
1) Python 没有注解驱动的容器后处理器，因此这里的 `@Scheduled` 只做**元数据标记**：
   把参数挂到函数属性 `__scheduled__` 上，等价于 JVM 上“注解可被反射读取”。
2) 真正“按时执行”需要一个调度器：本替身提供 `startScheduledTasks(bean)`（单个 Bean）
   与 `registerScheduled(bean, registrar)`（由 ``app/scheduler`` 汇总多个 Bean），
   把方法登记到 ``ScheduledTaskRegistrar``，与 Spring 的
   ``ScheduledAnnotationBeanPostProcessor`` 职责一一对应；
   **默认不自动启动**（测试/导入时不应偷偷起无限循环线程）。
   应用启动处（FastAPI 的 lifespan）调用 ``app.scheduler.start_scheduler()``。
3) 只实现本工程用到的属性：fixedRate / fixedDelay / initialDelay / cron，
   以及对应的 `xxxString` 形式（Spring 允许占位符 + 纯数值，如
   `@Scheduled(fixedRateString = "${reliability.compensation-interval-seconds:60}000")`）。
   cron 由 `ScheduledTaskRegistrar#addCronTask` 包成 `CronTrigger` 真正参与排期
   （见 ``org.springframework.scheduling.support.CronExpression``）。
4) 字符串属性在**启动调度时**才解析占位符（等价 Spring 在容器 refresh 时解析
   `@Value`/注解占位符），不是装饰时解析 —— 装饰发生在 import 阶段，Environment
   此刻可能尚未读到 application.yml。
5) 属性优先级与 Spring 一致：`cron` → `fixedRate` → `fixedDelay`（三者互斥，
   同时写在 Spring 里是非法配置；这里按同一顺序取第一个非空值）。
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, List, Optional, Tuple

from org.springframework.core.env.Environment import getEnvironment
from org.springframework.scheduling.config.ScheduledTaskRegistrar import ScheduledTaskRegistrar

__all__ = ["Scheduled", "scheduledMethods", "scheduledTrigger",
           "registerScheduled", "startScheduledTasks"]

log = logging.getLogger(__name__)

# `${key}` / `${key:default}` 后面允许拼接字面量，如 "${xxx:60}000"
_PLACEHOLDER_PREFIX = re.compile(r"^\$\{([^:}]+)(?::([^}]*))?\}(.*)$", re.DOTALL)


def Scheduled(cron: Optional[str] = None,
              fixedRate: Optional[int] = None,
              fixedDelay: Optional[int] = None,
              initialDelay: int = 0,
              fixedRateString: Optional[str] = None,
              fixedDelayString: Optional[str] = None,
              initialDelayString: Optional[str] = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """标记定时方法（等价 `@Scheduled(...)` 注解）。

    【Java→Python】Java 是**注解**，参数直接写在注解里；Python 用装饰器工厂还原。
    注解属性名保持 Java 驼峰（fixedRate/fixedRateString），便于与源码逐字对照。
    `fixedRateString` 与 `fixedRate` 互斥（Spring 校验二选一），这里允许同时传入但
    以 String 形式优先，避免调用方误写时静默取错值。
    """

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        fn.__scheduled__ = {
            "cron": cron,
            "fixedRate": fixedRate,      # 毫秒
            "fixedDelay": fixedDelay,    # 毫秒
            "initialDelay": initialDelay,  # 毫秒
            "fixedRateString": fixedRateString,      # 毫秒（原始字符串，启动时解析）
            "fixedDelayString": fixedDelayString,    # 毫秒（原始字符串，启动时解析）
            "initialDelayString": initialDelayString,  # 毫秒（原始字符串，启动时解析）
        }
        return fn

    return decorator


def _resolveMillis(raw: Any, property_name: str) -> Optional[int]:
    """把注解上的毫秒参数解析成 int（等价 Spring 的占位符解析 + 类型转换）。

    【Java→Python】Spring 支持 `fixedRateString = "${k:60}000"`：先替换 `${k:60}`
    得到 `"60" + "000"`，再整体转成 long。这里按同样步骤还原：
    1) 是 int（对应 fixedRate 的 long 字面量）→ 直接返回；
    2) 以 `${` 开头 → 取 key/默认值，与环境变量/配置合并后，拼上后面的字面量后缀；
    3) 其余情况当作纯数字字符串 → int()。
    与 Spring 一致：解析失败（非数字）直接抛异常，而不是悄悄忽略任务。
    """
    if raw is None:
        return None
    if isinstance(raw, int):
        return raw

    text = str(raw)
    match = _PLACEHOLDER_PREFIX.match(text)
    if match:
        key, default_text, suffix = match.group(1), match.group(2), match.group(3)
        # 默认值可能是空串（`${k:}`），Spring 视为空并把整串交给类型转换 → 报错
        default = int(default_text) if default_text not in (None, "") else None
        base = getEnvironment().getProperty(key, default)
        if base is None:
            raise KeyError("无法解析 @Scheduled 属性 %s 的占位符: %s" % (property_name, text))
        return int(str(base) + suffix) if suffix else int(base)

    try:
        return int(text)
    except ValueError:
        raise ValueError("@Scheduled 属性 %s 不是合法的毫秒数: %r" % (property_name, text))


def scheduledMethods(bean: Any) -> List[Callable[..., Any]]:
    """等价 `ScheduledAnnotationBeanPostProcessor` 的扫描结果：找出被标记的方法。"""
    found = []
    for name in dir(bean):
        if name.startswith("__"):
            continue
        attribute = getattr(bean, name, None)
        if callable(attribute) and getattr(attribute, "__scheduled__", None):
            found.append(attribute)
    return found


def _resolveCron(raw: Any) -> str:
    """解析 cron 属性上的占位符（等价 Spring 在 refresh 阶段解析注解占位符）。

    支持两种写法：
    - ``"0 30 2 * * ?"``                    → 原样返回
    - ``"${consistency.reconcile.cron:0 30 2 * * ?}"`` → 交给 Environment 按
      ``${key:default}`` 解析（与 ``@Value`` 同一套规则）
    """
    if not isinstance(raw, str):
        raise ValueError("@Scheduled 的 cron 属性必须是字符串: %r" % (raw,))
    if "${" not in raw:
        return raw.strip()
    return str(getEnvironment().value(raw, str)).strip()


def scheduledTrigger(config: dict,
                    method_name: str = "?") -> Tuple[str, Any]:
    """把 ``__scheduled__`` 元数据解析成调度三元组。

    返回 ``("cron", "0 30 2 * * ?")`` / ``("fixedRate", (毫秒, 初始延迟毫秒))`` /
    ``("fixedDelay", (毫秒, 初始延迟毫秒))``。

    【Java→Python】Spring 的判定顺序是 cron → fixedRate → fixedDelay（三者互斥）；
    `app/scheduler` 的启动清单（`/health`）与真正的登记都用本函数，
    保证“报告的任务”与“实际跑的任务”不会漂移。
    """
    if config.get("cron") is not None:
        return "cron", _resolveCron(config["cron"])
    # String 形式优先（Spring 校验二者互斥；这里按同样优先级取值）
    fixed_rate = (_resolveMillis(config.get("fixedRateString"), "fixedRateString")
                  if config.get("fixedRateString") is not None
                  else _resolveMillis(config.get("fixedRate"), "fixedRate"))
    fixed_delay = (_resolveMillis(config.get("fixedDelayString"), "fixedDelayString")
                   if config.get("fixedDelayString") is not None
                   else _resolveMillis(config.get("fixedDelay"), "fixedDelay"))
    initial_delay = (_resolveMillis(config.get("initialDelayString"), "initialDelayString")
                     if config.get("initialDelayString") is not None
                     else (config.get("initialDelay") or 0))
    if fixed_rate is not None:
        return "fixedRate", (fixed_rate, initial_delay)
    if fixed_delay is not None:
        return "fixedDelay", (fixed_delay, initial_delay)
    # Java 侧属性名写错是编译错误；替身只能运行期报错
    raise ValueError("@Scheduled 方法 %s 未指定 cron / fixedRate / fixedDelay" % method_name)


def registerScheduled(bean: Any,
                      registrar: ScheduledTaskRegistrar) -> List[Callable[..., Any]]:
    """把 bean 上被 ``@Scheduled`` 标记的方法登记到 registrar。

    等价 `ScheduledAnnotationBeanPostProcessor#processScheduled`。
    返回已登记的方法列表，便于启动日志与测试断言。
    """
    registered: List[Callable[..., Any]] = []
    for method in scheduledMethods(bean):
        kind, value = scheduledTrigger(method.__scheduled__, method.__name__)
        if kind == "cron":
            registrar.addCronTask(method, value)
        elif kind == "fixedRate":
            registrar.addFixedRateTask(method, value[0], value[1])
        else:
            registrar.addFixedDelayTask(method, value[0], value[1])
        registered.append(method)
    return registered


def startScheduledTasks(bean: Any,
                        scheduler: Any = None) -> ScheduledTaskRegistrar:
    """为单个 bean 启动 ``@Scheduled`` 任务（便捷入口，等价容器启动一个 Bean 的标记）。

    【Java→Python】Spring 用共享的 TaskScheduler 线程池；这里同样接受外部传入的
    ``ThreadPoolTaskScheduler``（``app/scheduler`` 就是全局共享一个），
    不传则使用 registrar 自带的（无调度器 → 不跑，见 ScheduledTaskRegistrar）。
    返回 ``ScheduledTaskRegistrar``，便于测试断言登记了哪些任务。
    """
    registrar = ScheduledTaskRegistrar()
    if scheduler is not None:
        registrar.setTaskScheduler(scheduler)
    registerScheduled(bean, registrar)
    registrar.afterPropertiesSet()
    return registrar
