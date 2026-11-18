# -*- coding: utf-8 -*-
"""Java <-> Python 方法级对照审计（行为等价性静态校验）。

对 Java 源文件逐一找出同路径的 `.py` 镜像文件，比较类名与方法名。

作用域：Python 端口只对齐 legacy 端口。``controller/v3`` 与 ``service/v3``
是尚未移植的 Java-only V3 架构，显式列为 out of scope（并在运行时自检：
一旦 Python 侧出现 V3 文件，本工具直接失败，强制重新评估豁免）。

输出分两档，避免把"继承来的 / 框架提供的 / Lombok 生成的"误判为缺失：

    Tier A  file-local miss but defined somewhere in the Python tree
            -> 通常是继承（BaseController#startPage）或共享工具方法，低风险
    Tier B  not defined anywhere in the Python tree
            -> **真正的行为缺口**，必须逐条确认

用法：
    python tools/check_parity.py             # 摘要 + Tier B 明细
    python tools/check_parity.py --tier-a    # 额外列出 Tier A
    python tools/check_parity.py --file Xxx  # 只看单个文件

退出码：0 = 无 Tier B 缺口；1 = 存在 Tier B 缺口。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE = PROJECT_ROOT.parent

SKIP_DIRS = {"target", ".git", ".idea", ".mimocode", ".vscode", "node_modules",
             "__pycache__", "out", "build", ".venv"}

#: 只对照两个业务模块的 Java 源。此前扫描整个 WORKSPACE，会把兄弟工程
#: ``car-monit-api-rust/.run/*.java`` 误判为 Tier B 缺口，导致本工具永久
#: exit 1、门禁失效（见 docs/迁移审阅报告.md §3.8）。
JAVA_SOURCE_ROOTS = tuple(
    WORKSPACE / module / "src" / "main" / "java"
    for module in ("pro-base-common", "pro-business-api")
)

# 这些词出现在"返回类型"位置时，说明抓到的是调用表达式而不是方法声明
# 例如 `return str(bytes, charset);` / `throw new RuntimeException(...)`
_CALL_KEYWORDS = {
    "return", "throw", "yield", "case", "assert", "new", "else", "do",
}

_NOT_METHODS = {
    "if", "for", "while", "switch", "catch", "return", "new", "synchronized",
    "do", "else", "try", "finally", "throw", "super", "this", "assert", "case",
    "instanceof", "yield", "with", "lambda", "record",
}

# 方法声明：必须从行首（允许缩进）开始，避免把 `sb.append(...)` / `new Foo(...)`
# 这类调用表达式当成声明。rtype 用于排除构造调用。
_JAVA_METHOD_RE = re.compile(
    r"^[ \t]*"
    r"(?:(?:public|protected|private|static|final|abstract|default|native"
    r"|synchronized|strictfp)\s+)*"
    r"(?:<[^>]*>\s*)?"
    r"(?P<rtype>[\w.$]+(?:\s*<[^;{}()]*>)?(?:\[\])*)?"
    r"[ \t]+(?P<name>\w+)[ \t]*\((?P<params>[^;{}]*)\)[ \t]*"
    r"(?:throws\s+[\w.,\s]+)?(?P<end>[{;])",
    re.MULTILINE,
)

# @interface 也要算类型声明（注解在 Java 里是类型）
_JAVA_TYPE_RE = re.compile(
    r"\b(?:class|interface|enum)\s+(\w+)|@interface\s+(\w+)", re.MULTILINE)

_PY_DEF_RE = re.compile(r"^[ \t]*def[ \t]+(\w+)[ \t]*\(", re.MULTILINE)
_PY_CLASS_RE = re.compile(r"^[ \t]*class[ \t]+(\w+)", re.MULTILINE)

# Lombok @Data 生成的访问器；Python 侧由 JavaBean.__getattr__ 动态提供
_ACCESSOR_RE = re.compile(r"^(?:get|set|is)[A-Z]")

# 已人工逐条核实的等价映射（Java 侧独有写法 → Python 侧的合法替代实现）。
# 新增条目必须写明理由，否则这个门禁就失去意义。
_DOCUMENTED_EQUIVALENTS: dict[tuple[str, str], str] = {
    ("pro-base-common/src/main/java/com/ruoyi/common/config/annotation/PermissionAnon.java",
     "PermissionAnon"):
        "@interface → 模块级标记装饰器函数（PermissionAnon.py）",
    ("pro-base-common/src/main/java/com/ruoyi/common/config/annotation/ValidHeader.java",
     "ValidHeader"):
        "@interface → 模块级注解工厂函数（ValidHeader.py）",
    ("pro-base-common/src/main/java/com/ruoyi/common/utils/CommonUtil.java",
     "CommonUtil"):
        "static 工具类 → 模块级函数（Java 静态方法在 Python 无意义，调用点仍写 CommonUtil.isNotBlank）",
    ("pro-base-common/src/main/java/com/ruoyi/common/utils/RedisUtil.java",
     "del"):
        "del 是 Python 关键字，方法改名为 delete（文件头已说明，调用点已同步）",
    ("pro-base-common/src/main/java/com/ruoyi/common/utils/spring/SpringUtils.java",
     "postProcessBeanFactory"):
        "BeanFactoryPostProcessor 回调 → 模块级 register_bean()",
    ("pro-base-common/src/main/java/com/ruoyi/common/utils/spring/SpringUtils.java",
     "setApplicationContext"):
        "ApplicationContextAware 回调 → 模块级 set_application_context()",
    ("pro-base-common/src/main/java/com/ruoyi/common/core/controller/BaseController.java",
     "setValue"):
        "匿名 PropertyEditorSupport 子类继承的 setValue；Python 侧用闭包完成日期绑定",
    ("pro-business-api/src/main/java/com/ruoyi/base/service/optimization/LargeScaleQueryService.java",
     "NamedThreadFactory"):
        "private static 内部类 → 模块级 _NamedThreadFactory（前缀下划线，外部不可见）",
    ("pro-business-api/src/main/java/com/ruoyi/base/service/optimization/UnifiedExportService.java",
     "NamedThreadFactory"):
        "private static 内部类 → 模块级 _NamedThreadFactory（前缀下划线，外部不可见）",
}

# ---------------------------------------------------------------------------
# V3 作用域边界（P1：check_parity 红）
#
# 事实依据（已核对 git 历史）：
#   * V3 的 feature 提交（8d810b9..382fb84）只改 Java 侧，从未改 car-monit-api-python；
#   * Python 树中不存在任何 controller/v3、service/v3 文件，也未实现 ES 主路径、
#     Outbox/Kafka 同步、PIT 深分页、DWS ETL；
#   * Python 端口定位是 legacy 端口的等价实现，V3 是 Java-only 的新架构。
#
# 因此这不是“镜像漏同步”，而是 checker 未区分“应当逐一镜像的 legacy 端口”和
# “尚未移植的 Java-only V3”。这里显式列出作用域，并在下方做反向自检：
# 一旦 Python 树开始出现 V3 文件，工具会直接失败，强制维护者重新审视豁免，
# 避免作用域边界长期掩盖真实漂移。
# ---------------------------------------------------------------------------
_OUT_OF_SCOPE_PREFIXES: tuple[str, ...] = (
    "pro-business-api/src/main/java/com/ruoyi/base/controller/v3/",
    "pro-business-api/src/main/java/com/ruoyi/base/service/v3/",
    # 以下为 Java-only 运维/基础设施代码，Python legacy 端口不实现：
    # Spring MVC 内部端点令牌拦截器（只保护 Java 侧 /api/v3/** 与导出端点）。
    "pro-business-api/src/main/java/com/ruoyi/base/config/InternalEndpointGuardConfig.java",
    # Native 镜像的 SqlSessionFactory 注册器（Java native-image 特有）。
    "pro-business-api/src/main/java/com/ruoyi/base/config/NativeMapperSqlSessionFactoryRegistrar.java",
    # 系统基础服务客户端（Java 侧内部集成，Python 端口无对应端点）。
    "pro-business-api/src/main/java/com/ruoyi/base/forest/SysBaseClient.java",
)

#: legacy 控制器上仅因 V3 双路径（ES/legacy）而新增的方法；Python 仍为单一 legacy 路径。
V3_JAVA_ONLY_METHODS: dict[str, set[str]] = {
    "pro-business-api/src/main/java/com/ruoyi/base/controller/LargeScaleQueryController.java": {
        "addCode", "addResolvedCodes", "asString", "buildV3ExportRequest",
        "downloadExport", "extractFuzzyStringFields", "filePartCount", "isV3Mode",
    },
    "pro-business-api/src/main/java/com/ruoyi/base/controller/OdsLwzxsfsjFeeRecords01Controller.java": {
        "applyDataScope", "decorateLegacy", "errorResult",
        "listFromEs", "listLegacy", "toDomains",
    },
    "pro-business-api/src/main/java/com/ruoyi/base/controller/OdsRtSzdnSnapshotFlowAddcodeController.java": {
        "applyDataScope", "decorate", "errorResult",
        "listFromEs", "listLegacy", "toDomains",
    },
    "pro-business-api/src/main/java/com/ruoyi/base/controller/SysUtilController.java": {
        "asString", "buildTrailInfos", "carTrackQueryByCarNoFromEs",
        "carTrackQueryByCarNoLegacy", "toTrailTracks",
    },
    # Redis 缓存写入器的 Java 侧 CompletableFuture 异步方法；Python 用同步实现，
    # 不镜像这两个方法签名（java-V3 分支对应 Java 源码亦无此方法）。
    "pro-base-common/src/main/java/com/ruoyi/common/config/writer/RetRedisCacheWriter.java": {
        "retrieve", "store",
    },
    # Flink 作业构建 KafkaSource 的 Java 侧私有方法；Python 端口不实现 Flink 作业。
    "pro-business-api/src/main/java/com/ruoyi/base/flink/VehicleTrackFlinkJob.java": {
        "buildKafkaSource",
    },
}


def is_v3_out_of_scope(rel: str) -> bool:
    return any(rel.startswith(prefix) for prefix in _OUT_OF_SCOPE_PREFIXES)


def python_v3_files() -> list[str]:
    """反向自检：若 Python 树已出现 V3 镜像，说明作用域豁免需要重新评估。"""
    root = PROJECT_ROOT / "pro-business-api" / "src" / "main" / "java" / "com" / "ruoyi" / "base"
    found: list[str] = []
    for sub in ("controller/v3", "service/v3"):
        if not (root / sub).exists():
            continue
        for directory, filenames in walk(root / sub):
            for name in filenames:
                if name.endswith(".py"):
                    found.append((directory / name).relative_to(PROJECT_ROOT).as_posix())
    return sorted(found)



def strip_java_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", " ", source, flags=re.DOTALL)
    source = re.sub(r"//[^\n]*", " ", source)
    return source


def java_declarations(java_path: Path) -> tuple[set[str], set[str]]:
    source = strip_java_comments(java_path.read_text(encoding="utf-8", errors="replace"))
    types: set[str] = set()
    for a, b in _JAVA_TYPE_RE.findall(source):
        types.add(a or b)

    methods: set[str] = set()
    for match in _JAVA_METHOD_RE.finditer(source):
        name = match.group("name")
        rtype = (match.group("rtype") or "").strip()
        if name in _NOT_METHODS or name in types:
            continue                              # 控制结构 / 构造器
        if rtype in _CALL_KEYWORDS or rtype.endswith("."):
            continue                              # 调用表达式，不是声明
        if name.isupper():
            continue                              # 枚举常量 ALL(0)/NORMAL("0")
        methods.add(name)
    return types, methods


def py_declarations(py_path: Path) -> tuple[set[str], set[str], bool]:
    """返回 (类名, 方法名, 是否继承 JavaBean)。"""
    source = py_path.read_text(encoding="utf-8", errors="replace")
    classes = set(_PY_CLASS_RE.findall(source))
    methods = {n for n in _PY_DEF_RE.findall(source) if not n.startswith("__")}
    uses_java_bean = bool(re.search(r"^class[ \t]+\w+[ \t]*\([^)]*JavaBean", source, re.MULTILINE))
    return classes, methods, uses_java_bean


def walk(root: Path):
    import os
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        yield Path(dirpath), filenames


def collect_python_global() -> tuple[set[str], set[str]]:
    """整个 Python 树里出现过的类名/方法名，用于 Tier A/B 判定。"""
    classes: set[str] = set()
    methods: set[str] = set()
    roots = [PROJECT_ROOT] + [PROJECT_ROOT / p for p in (
        "pro-base-common/src/main/java", "pro-business-api/src/main/java",
        "com", "java", "javax", "org")]
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for directory, filenames in walk(root):
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                path = directory / name
                if path in seen:
                    continue
                seen.add(path)
                c, m, _ = py_declarations(path)
                classes |= c
                methods |= m
    return classes, methods


def main() -> int:
    show_tier_a = "--tier-a" in sys.argv
    only = None
    if "--file" in sys.argv:
        only = sys.argv[sys.argv.index("--file") + 1].replace("\\", "/")

    # 反向自检：Python 侧出现 V3 镜像时必须重新评估作用域豁免
    v3_py = python_v3_files()
    if v3_py:
        print("检测到 Python 侧已出现 V3 镜像文件，作用域豁免失效，请移除 _OUT_OF_SCOPE_PREFIXES：")
        for rel in v3_py:
            print(f"  {rel}")
        return 1

    global_classes, global_methods = collect_python_global()

    checked = exact = 0
    out_of_scope = 0
    tier_a: list[tuple[str, list[str], list[str]]] = []
    tier_b: list[tuple[str, list[str], list[str]]] = []

    java_files = sorted(
        d / n
        for root in JAVA_SOURCE_ROOTS
        for d, ns in walk(root)
        for n in ns if n.endswith(".java")
    )
    for java_path in java_files:
        rel = java_path.relative_to(WORKSPACE).as_posix()
        if only and only not in rel:
            continue
        if is_v3_out_of_scope(rel):
            out_of_scope += 1
            continue
        py_path = PROJECT_ROOT / (rel[:-5] + ".py")
        if not py_path.exists():
            tier_b.append((rel, ["<entire file missing>"], []))
            continue

        checked += 1
        j_types, j_methods = java_declarations(java_path)
        p_classes, p_methods, uses_java_bean = py_declarations(py_path)

        # Lombok 访问器由 JavaBean 动态生成，不算缺失
        if uses_java_bean:
            j_methods = {n for n in j_methods if not _ACCESSOR_RE.match(n)}

        # V3 双路径专属方法：Python 端口保持单一 legacy 路径，不算漂移
        v3_only = V3_JAVA_ONLY_METHODS.get(rel, set())
        missing = sorted(m for m in j_methods - p_methods if m not in v3_only)
        # static 工具类在 Python 侧是模块级函数，所以 def 也算类型已实现
        p_names = p_classes | p_methods
        missing_classes = sorted(t for t in j_types if t not in p_names)

        if not missing and not missing_classes:
            exact += 1
            continue

        hard_methods = [m for m in missing
                        if m not in global_methods
                        and (rel, m) not in _DOCUMENTED_EQUIVALENTS]
        soft_methods = [m for m in missing if m not in hard_methods]
        hard_classes = [c for c in missing_classes
                        if c not in global_classes
                        and (rel, c) not in _DOCUMENTED_EQUIVALENTS]

        if hard_methods or hard_classes:
            tier_b.append((rel, hard_methods, hard_classes))
        if soft_methods:
            tier_a.append((rel, soft_methods, []))

    print("=" * 78)
    print(f"checked files        : {checked}")
    print(f"fully matched        : {exact}")
    print(f"out of scope (Java-only V3) : {out_of_scope} file(s) "
          f"(controller/v3 + service/v3；Python 端口未实现 V3)")
    print(f"documented equivalences : {len(_DOCUMENTED_EQUIVALENTS)} known entry(ies)")
    print(f"Tier A (shared/inherited) : {len(tier_a)} file(s) with {sum(len(m) for _, m, _ in tier_a)} name(s)")
    print(f"Tier B (real gaps)        : {len(tier_b)} file(s)")
    print("=" * 78)

    if tier_b:
        print("\n### Tier B -- 未在 Python 树中任何位置定义，且未登记为已知等价映射")
        for rel, methods, classes in tier_b:
            print(f"\n{rel}")
            if classes:
                print(f"  type missing : {', '.join(classes)}")
            for name in methods:
                print(f"  method missing : {name}")

    if show_tier_a and tier_a:
        print("\n### Tier A -- 本文件未定义，但 Python 树中其他地方有（继承/共享）")
        for rel, methods, _ in tier_a:
            print(f"  {rel}: {', '.join(methods)}")

    return 0 if not tier_b else 1


if __name__ == "__main__":
    sys.exit(main())
