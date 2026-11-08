# -*- coding: utf-8 -*-
"""Secret 扫描门禁（gitleaks 等价的最小实现，阻断 B2）。

只扫描 **git 已跟踪** 的 Python 工程文件（不扫 `.venv` / 运行产物 / 未跟踪
证据文件），因此结果可复现，也不会把本机临时口令当成泄漏。

规则分两类：

1. **本仓库已知泄漏值**：``OpenGauss@123`` / ``redis321``（历史文档与注释），
   仅允许出现在本脚本自身的拼接字面量中（脚本排除自己）。
2. **通用高置信度模式**：PEM 私钥、AWS Access Key、GitHub/Slack token，
   以及 yml 中**未走 `${ENV}` 占位符**的 password/secret/token 值
   （含被注释掉的写法，防止把口令注释回仓库）。

退出码：0 = 无发现；1 = 有发现（CI / ``tools/run_checks.ps1`` 门禁使用）。

用法::

    .venv\\Scripts\\python.exe tools\\check_secrets.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()

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

#: 通用高置信度模式（文件名: 正则）
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


def _tracked_files() -> list[Path]:
    """列出 git 已跟踪的文件（相对 ROOT）。"""
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(ROOT),
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        print("WARN: git ls-files 失败，退化为扫描工作树", file=sys.stderr)
        return [path for path in ROOT.rglob("*")
                if path.is_file() and ".venv" not in path.parts
                and ".git" not in path.parts]
    return [ROOT / name for name in result.stdout.split("\0") if name]


def _is_candidate(path: Path) -> bool:
    if path.resolve() == SELF:
        return False
    if path.suffix.lower() in _SKIP_SUFFIXES:
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
    return value.startswith("${") or value.startswith("$") or value.startswith("<")


def scan() -> list[str]:
    findings: list[str] = []
    for path in _tracked_files():
        if not _is_candidate(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _is_text(text):
            continue
        rel = path.relative_to(ROOT).as_posix()
        for line_no, line in enumerate(text.splitlines(), 1):
            for literal in _LEAKED_LITERALS:
                if literal in line:
                    findings.append("%s:%d 已知泄漏值（%s）" % (rel, line_no, literal[:4] + "..."))
            for name, pattern in _GENERIC_RULES:
                if pattern.search(line):
                    findings.append("%s:%d 通用规则命中：%s" % (rel, line_no, name))
            if path.suffix.lower() in (".yml", ".yaml"):
                matched = _YML_SECRET.match(line)
                if matched and not _placeholder(matched.group("value")):
                    findings.append("%s:%d yml 明文口令（应改为 ${ENV:} 占位符）"
                                    % (rel, line_no))
    return findings


def main() -> int:
    findings = scan()
    if not findings:
        print("secret scan: no findings (%d tracked files)" % len(_tracked_files()))
        return 0
    print("secret scan: %d finding(s)" % len(findings))
    for finding in findings:
        print("  " + finding)
    return 1


if __name__ == "__main__":
    sys.exit(main())
