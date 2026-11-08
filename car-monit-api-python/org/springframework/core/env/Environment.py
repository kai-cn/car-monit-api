# -*- coding: utf-8 -*-
"""org.springframework.core.env.Environment

【无 Java 源文件：框架类替身】
Java 侧来自 Spring Framework jar：org.springframework.core.env.Environment，
业务代码通过 `@Value("${sync.batch-size:1000}")` 间接依赖它。

【Java→Python 关键差异】
1) Spring 在容器启动时由 `PropertySourcesPlaceholderConfigurer` 解析 `${key:default}`
   并**反射注入**私有字段；Python 无容器、无反射注入，改为在构造函数里显式调用
   `environment.value("${sync.batch-size:1000}", int)` 得到同值（见 SnapshotFlowSyncService）。
2) Spring 的配置来源是 application.yml/.properties + 系统属性 + 环境变量等多级
   PropertySource；这里按同等优先级实现：
       环境变量（SYNC_BATCH_SIZE） > application.yml > 占位符内默认值
   注意 Spring 的 SystemEnvironmentPropertySource 会把 `a.b-c` 松弛绑定为 `A_B_C`，
   本替身照此实现（`.`/`-` → `_`，转大写）。
3) 本机可能没有 PyYAML（默认解释器为 3.10 且未装依赖），因此内置一个**极简 YAML 子集
   解析器**：只支持「缩进嵌套的 key: value 标量」，足以读取 application.yml 的
   `sync.*`；遇到列表/多行字符串等复杂结构时跳过而不报错。
4) Java 的 `@Value` 找不到占位符且无默认值 → 容器启动直接抛
   IllegalArgumentException；这里同样抛 KeyError，不做静默兜底，避免隐藏配置错误。
"""
from __future__ import annotations

import os
import re
from typing import Any, Callable, Dict, Optional

__all__ = ["Environment", "getEnvironment"]

# ${key:default}；默认值可省略。key 内允许中划线/点号。
_PLACEHOLDER_PATTERN = re.compile(r"^\$\{([^:}]+)(?::(.*))?\}$", re.DOTALL)

# P0-6：属性**值**里的嵌套占位符（如 `password: ${DB_PASSWORD:}`），
# 对应 Spring 的 PropertySourcesPlaceholderConfigurer 对属性值的递归解析。
_PLACEHOLDER_VALUE_RE = re.compile(r"\$\{([^:}]+)(?::([^}]*))?\}")

# 进程级单例：等价 Spring 容器内唯一的 Environment Bean
_DEFAULT_ENVIRONMENT: Optional["Environment"] = None

# 【Java→Python】Spring Boot 启动时自动加载 classpath:application.yml；
# 这里以 Environment.py 所在位置推算出 refactor 根目录，再把原工程的 application.yml
# 加入默认配置源（文件不存在时静默跳过，等价“没有配置文件”）。
_REFACTOR_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
_DEFAULT_CONFIG_FILES = [
    os.path.join(_REFACTOR_ROOT, "pro-business-api", "src", "main", "resources", "application.yml"),
]


def _relaxed_names(key: str) -> list:
    """Spring 松弛绑定：`sync.batch-size` → `SYNC_BATCH_SIZE`。"""
    relaxed = key.replace(".", "_").replace("-", "_").upper()
    # 同时保留原样（环境变量名本身可能就带点号，极少数场景）
    return [relaxed, key]


def _parse_scalar(raw: str) -> Any:
    """把 YAML 标量转成 Python 值（只覆盖工程内出现的类型）。"""
    text = raw.strip()
    if not text:
        return ""
    # 去掉行尾注释（application.yml 里 `# xxx` 常见）；不处理引号内的 #
    if text[0] not in ("'", '"'):
        comment_at = text.find(" #")
        if comment_at >= 0:
            text = text[:comment_at].strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        return text[1:-1]
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~"):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def _load_yaml_flat(path: str) -> Dict[str, Any]:
    """极简 YAML 读取：缩进嵌套映射 → 扁平化的点号 key。

    【Java→Python】Spring 用 SnakeYAML 解析完整 YAML；这里只实现子集，
    复杂节点（列表、块标量、锚点）会被跳过 —— 对 `@Value` 标量注入无影响。
    """
    flat: Dict[str, Any] = {}
    if not os.path.isfile(path):
        return flat

    # Spring Boot 支持多文档（---）；这里只看第一个文档，够用
    stack = []  # [(indent, prefix)]
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.startswith("---"):
                break
            if stripped.startswith("- "):
                # 列表项：@Value 不会引用列表下标，直接跳过
                continue
            if ":" not in stripped:
                continue
            indent = len(line) - len(line.lstrip(" "))
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            # 弹出比当前缩进更深的层级
            while stack and indent <= stack[-1][0]:
                stack.pop()
            prefix = ".".join([item[1] for item in stack] + [key])
            if value == "":
                # 空值视为「下一层是映射」
                stack.append((indent, key))
                continue
            flat[prefix] = _parse_scalar(value)
    return flat


class Environment:
    """`@Value` 占位符解析器（Spring Environment 的最小子集）。"""

    def __init__(self, config_files: Optional[list] = None) -> None:
        """构造环境。

        【Java→Python】`config_files=None` 时**默认加载工程的 application.yml**：
        Spring Boot 启动时 Environment 天然包含 application.yml，服务里 `new Environment()`
        等价于取容器内的 Environment，而不是一个“空配置”。若传空列表 [] 则不加载任何文件。

        P0-6：默认还会叠加同目录的 ``application-local.yml``（gitignored）作为
        最高优先级的**文件**源——真实口令等敏感值写在里面，仓库里的
        application.yml 只保留 ``${ENV:}`` 占位符（对应 Spring 的 profile 覆盖
        语义）。环境变量优先级仍高于一切文件。
        """
        self._properties: Dict[str, Any] = {}
        files = _DEFAULT_CONFIG_FILES if config_files is None else config_files
        if config_files is None:
            local_overlays = [
                os.path.join(os.path.dirname(path), "application-local.yml")
                for path in files
                if os.path.isfile(os.path.join(os.path.dirname(path), "application-local.yml"))
            ]
            files = files + local_overlays
        for path in files:
            for key, value in _load_yaml_flat(path).items():
                # 后加载的覆盖先加载的（等价 Spring 的 PropertySource 顺序）
                self._properties[key] = value

    # ------------------------------------------------------------------ 取值
    def getProperty(self, key: str, default: Any = None) -> Any:
        """等价 environment.getProperty(key)：环境变量优先，其次配置文件。

        P0-6：配置文件值里的 ``${KEY:default}`` 占位符会按 Spring 的占位符
        解析语义展开（环境变量 > 已加载属性 > 默认值，最多递归 5 层）。

        B1（2026-11-08 审阅）：环境变量分支必须**原样返回字符串**。
        Spring 的 ``SystemEnvironmentPropertySource`` 永远返回 String，从不把
        环境变量当 YAML 标量解析；此前这里调用了 ``_parse_scalar``，导致当
        占位符名恰好等于松弛名（如 ``...MASTER_PASSWORD``）时口令被改写：
        ``00123`` → ``123``、``true`` → ``True``、``null`` → 空串、
        含 ``" #"`` 的值被截断。类型转换统一交给 ``value()`` 的目标类型完成。
        """
        for candidate in _relaxed_names(key):
            if candidate in os.environ:
                return os.environ[candidate]
        if key in self._properties:
            return self._resolve_placeholders(self._properties[key])
        return default

    def _resolve_placeholders(self, value: Any, depth: int = 0) -> Any:
        """展开属性值里的嵌套 ``${KEY:default}``（P0-6）。"""
        if not isinstance(value, str) or "${" not in value or depth > 5:
            return value

        def _replace(match: Any) -> str:
            key = match.group(1).strip()
            default_text = match.group(2)
            for candidate in _relaxed_names(key):
                if candidate in os.environ:
                    return os.environ[candidate]
            if key in self._properties:
                return str(self._properties[key])
            if default_text is not None:
                return default_text
            return match.group(0)  # 解析不到且无默认：保留原文，问题对调用方可见

        return self._resolve_placeholders(_PLACEHOLDER_VALUE_RE.sub(_replace, value),
                                           depth + 1)

    def value(self, placeholder: str, target_type: Callable[[Any], Any] = str) -> Any:
        """解析 `@Value` 表达式。

        用法：
            env.value("${sync.batch-size:1000}", int)   # → 1000
            env.value("${sync.full-sync-enabled:true}", bool)
        """
        match = _PLACEHOLDER_PATTERN.match((placeholder or "").strip())
        if not match:
            # @Value 也可以直接写字面量（如 @Value("hello")）
            return target_type(placeholder)
        key = match.group(1).strip()
        default_text = match.group(2)
        raw = self.getProperty(key, None)
        if raw is None:
            if default_text is None:
                # 与 Spring 一致：无默认值且解析不到 → 启动失败
                raise KeyError("无法解析占位符 ${%s}：配置项缺失且无默认值" % key)
            raw = _parse_scalar(default_text)
        return self._convert(raw, target_type)

    @staticmethod
    def _convert(raw: Any, target_type: Callable[[Any], Any]) -> Any:
        """按 Java 的注入类型转换（Integer/Boolean/Long/String）。"""
        if target_type is str or target_type is None:
            return raw if isinstance(raw, str) else str(raw)
        if target_type is bool:
            if isinstance(raw, bool):
                return raw
            return str(raw).strip().lower() in ("true", "1", "yes", "y")
        try:
            return target_type(raw)
        except (TypeError, ValueError):
            # Java 的 ConversionService 失败会抛异常，这里同样不静默
            raise ValueError("配置值 %r 无法转换为 %s" % (raw, target_type))


def getEnvironment() -> Environment:
    """获取进程级 Environment（等价注入 Spring 的 Environment Bean）。

    【Java→Python】默认加载工程的 application.yml（若存在），使 @Scheduled 的
    `fixedRateString` 等占位符能取到真实配置，而不是永远落回注解默认值。
    """
    global _DEFAULT_ENVIRONMENT
    if _DEFAULT_ENVIRONMENT is None:
        _DEFAULT_ENVIRONMENT = Environment()
    return _DEFAULT_ENVIRONMENT
