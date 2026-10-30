# -*- coding: utf-8 -*-
"""Java <-> Python 方法级对照审计（行为等价性静态校验）。

对 219 个 Java 源文件逐一找出同路径的 `.py` 镜像文件，比较类名与方法名。

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

    global_classes, global_methods = collect_python_global()

    checked = exact = 0
    tier_a: list[tuple[str, list[str], list[str]]] = []
    tier_b: list[tuple[str, list[str], list[str]]] = []

    for java_path in sorted(
            (d / n for d, ns in walk(WORKSPACE) for n in ns if n.endswith(".java"))):
        rel = java_path.relative_to(WORKSPACE).as_posix()
        if only and only not in rel:
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

        missing = sorted(j_methods - p_methods)
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
