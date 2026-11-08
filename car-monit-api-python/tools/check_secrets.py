# -*- coding: utf-8 -*-
"""Secret 扫描门禁（gitleaks 等价的最小实现，阻断 B2 / 中危复核）。

扫描范围（2026-11-08 扩围）：**git 仓库根**，包含
``git ls-files --cached``（已跟踪）与 ``--others --exclude-standard``（未跟踪但
未被 gitignore 的文件）——因此 ``docs/`` 下未入库的审阅报告也会被覆盖。
``.git`` / ``.venv`` / 构建产物 / IDE 元数据目录会被排除。

规则：

1. **本仓库已知泄漏值**：``OpenGauss@123`` / ``redis321``（历史文档与注释），
   仅允许出现在本脚本自身的拼接字面量中（脚本排除自己）。
2. **通用高置信度模式**：PEM 私钥、AWS Access Key、GitHub/Slack token。
3. **配置明文口令**：yml/yaml、properties、.env 中未走 ``${ENV}`` 占位符的
   password/secret/token 值（含注释掉的写法）。

已知历史遗留文件（Java/Go/Debezium/setup 等非 Python 工程）在
``_ALLOWLIST_PATH_PREFIXES`` 中显式豁免，并注明"待轮换后移除"；新增泄漏
（尤其是 Python 工程与 ``docs/``）不会被豁免。

退出码：0 = 无发现；1 = 有发现（CI / ``tools/run_checks.ps1`` 门禁使用）。

用法::

    .venv\\Scripts\\python.exe tools\\check_secrets.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PY_ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()


def _repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"], cwd=str(PY_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip())
    return PY_ROOT


REPO_ROOT = _repo_root()

#: fail-open 保护：扫描文件数低于该阈值直接判失败（避免在错误目录扫 0 个文件还 exit 0）
MIN_FILES = 100

#: 历史泄漏值（拆开拼接，避免扫描器把本脚本自身当成泄漏）
_LEAKED_LITERALS = (
    "Open" + "Gauss@123",
    "redis" + "321",
)

#: 二进制/无需扫描的后缀
_SKIP_SUFFIXES = {
    ".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".png", ".jpg", ".jpeg",
    ".gif", ".webp", ".ico", ".pdf", ".docx", ".xlsx", ".pptx", ".zip",
    ".gz", ".tar", ".bz2", ".7z", ".jar", ".class", ".rdb", ".db", ".sqlite",
}

#: 目录名（任一层命中即跳过）
_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "target", "coverage", "logs",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    ".mimocode", ".codebuddy", ".idea", ".vscode", ".trae", ".screenshots",
    "dist", "build", "out",
}

#: 已知历史遗留明文口令文件（非 Python 工程；轮换/改造后应移除对应条目）
_ALLOWLIST_PATH_PREFIXES: tuple[str, ...] = ()

#: 通用高置信度模式
_GENERIC_RULES = (
    ("pem-private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
)

#: yml 中未使用占位符的口令/密钥值（含注释掉的写法）
_YML_SECRET = re.compile(
    r"^\s*#?\s*(?:password|passwd|secret|token)\s*:\s*(?P<value>[^\s#]+)",
    re.IGNORECASE,
)

#: .properties / .env 中未使用占位符的口令/密钥值
_KEY_VALUE_SECRET = re.compile(
    r"^\s*#?\s*(?:[A-Za-z0-9_.-]*(?:password|passwd|secret|token)"
    r"[A-Za-z0-9_.-]*)\s*=\s*(?P<value>[^\s#]+)",
    re.IGNORECASE,
)

#: 文档/脚本等自由文本里的 ``password: xxx`` / ``password=xxx``（实测 notes.md 漏报）
_TEXT_SECRET = re.compile(
    r"(?i)\bpassword\s*[:=]\s*[`'\"]?(?P<value>[^\s'\"`,;#]+)",
)

#: 文本规则适用的扩展名（yml/properties/env 走上面的专门规则，避免重复）
_TEXT_SUFFIXES = {
    ".md", ".markdown", ".txt", ".sh", ".bash", ".ps1", ".json",
    ".conf", ".ini", ".cfg",
}


def _files() -> list[Path]:
    """仓库根下所有已跟踪 + 未跟踪（非 ignore）文件。"""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=str(REPO_ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print("WARN: git ls-files 失败，退化为扫描工作树", file=sys.stderr)
        paths = [path for path in REPO_ROOT.rglob("*") if path.is_file()]
    else:
        paths = [REPO_ROOT / name for name in result.stdout.split("\0") if name]
    return [path for path in paths
            if not any(part in _SKIP_DIRS for part in path.parts)]


def _is_candidate(path: Path, rel: str) -> bool:
    if path.resolve() == SELF:
        return False
    if path.suffix.lower() in _SKIP_SUFFIXES:
        return False
    if rel.startswith(_ALLOWLIST_PATH_PREFIXES):
        return False
    try:
        return path.stat().st_size <= 2 * 1024 * 1024
    except OSError:
        return False


def _is_text(text: str) -> bool:
    return "\x00" not in text


def _placeholder(value: str) -> bool:
    value = value.strip().strip("'\"")
    if not value:
        return True
    return value.startswith(("${", "$", "<", "{{", "["))


def _config_kind(path: Path) -> str:
    name = path.name.lower()
    suffix = path.suffix.lower()
    if suffix in (".yml", ".yaml"):
        return "yml"
    if suffix == ".properties":
        return "properties"
    if name == ".env" or name.startswith(".env."):
        return "env"
    return ""


def scan() -> list[str]:
    findings: list[str] = []
    files = _files()
    for path in files:
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        if not _is_candidate(path, rel):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _is_text(text):
            continue
        kind = _config_kind(path)
        text_rule = path.suffix.lower() in _TEXT_SUFFIXES
        for line_no, line in enumerate(text.splitlines(), 1):
            for literal in _LEAKED_LITERALS:
                if literal in line:
                    findings.append("%s:%d 已知泄漏值（%s）"
                                    % (rel, line_no, literal[:4] + "..."))
            for name, pattern in _GENERIC_RULES:
                if pattern.search(line):
                    findings.append("%s:%d 通用规则命中：%s" % (rel, line_no, name))
            if kind == "yml":
                matched = _YML_SECRET.match(line)
            elif kind in ("properties", "env"):
                matched = _KEY_VALUE_SECRET.match(line)
            else:
                matched = None
            if matched and not _placeholder(matched.group("value")):
                findings.append("%s:%d 配置明文口令（应改为 ${ENV:} 占位符）"
                                % (rel, line_no))
            if text_rule:
                text_matched = _TEXT_SECRET.search(line)
                if (text_matched
                        and not _placeholder(text_matched.group("value"))):
                    findings.append("%s:%d 文本明文口令（password: value）"
                                    % (rel, line_no))
    return findings


def main() -> int:
    files = _files()
    if len(files) < MIN_FILES:
        print("secret scan: FAIL-OPEN GUARD: only %d file(s) found under %s "
              "(expected >= %d); refusing to pass"
              % (len(files), REPO_ROOT, MIN_FILES))
        return 1
    findings = scan()
    if not findings:
        print("secret scan: no findings (%d files under %s)" % (len(files), REPO_ROOT))
        return 0
    print("secret scan: %d finding(s)" % len(findings))
    for finding in findings:
        print("  " + finding)
    return 1


if __name__ == "__main__":
    sys.exit(main())
