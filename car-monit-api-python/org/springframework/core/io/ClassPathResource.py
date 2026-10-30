# -*- coding: utf-8 -*-
"""org.springframework.core.io.ClassPathResource

【无 Java 源文件：框架类替身】
Java 侧来自 spring-core 的 ``org.springframework.core.io.ClassPathResource``。
本工程用法（EsIndexManageService.buildSettingsAndMapping）：
    ClassPathResource resource = new ClassPathResource(classpathMapping);
    if (!resource.exists()) { throw new IOException(...); }
    try (InputStream is = resource.getInputStream()) { ... }

【Java→Python 关键差异】
1) **classpath 在 Java 里是“打包后的 classpath 根”**（jar 内或
   ``target/classes``）。Python 没有这个概念，替身把 classpath 映射为源码树里的
   ``<module>/src/main/resources/<path>`` —— 本工程即
   ``pro-business-api/src/main/resources/es/index/*.json``。
2) 查找顺序与 Java 类加载一致：按模块顺序探测
   （``pro-business-api`` → ``pro-base-common``），命中即返回。
3) ``exists()`` / ``getInputStream()`` 保持原方法名与语义；
   找不到文件时 ``getInputStream`` 抛 ``FileNotFoundError``（Java 抛 IOException）。
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from java.io.InputStream import InputStream

__all__ = ["ClassPathResource"]

#: refactor 根目录（本文件位于 refactor/org/springframework/core/io/ClassPathResource.py，
#: 需要向上 5 层：io → core → springframework → org → refactor）
_REFACTOR_ROOT = Path(__file__).resolve().parents[4]

#: 【Java→Python】classpath 根 → 源码树中的 resources 目录（按探测顺序）
_CLASSPATH_ROOTS = (
    _REFACTOR_ROOT / "pro-business-api" / "src" / "main" / "resources",
    _REFACTOR_ROOT / "pro-base-common" / "src" / "main" / "resources",
)


class ClassPathResource(object):
    """``ClassPathResource`` 的替身（映射到源码树的 resources 目录）。"""

    def __init__(self, path: str, class_loader: Optional[object] = None) -> None:
        # 与 Java 一致：去掉前缀斜杠（classpath:/es/index/x.json → es/index/x.json）
        self.path: str = str(path or "").lstrip("/")
        self.classLoader = class_loader
        self._file: Optional[Path] = self._resolve()

    # ------------------------------------------------------------------ 定位
    def _resolve(self) -> Optional[Path]:
        for root in _CLASSPATH_ROOTS:
            candidate = root / self.path
            if candidate.is_file():
                return candidate
        return None

    def exists(self) -> bool:
        """对应 ``exists()``。"""
        return self._file is not None

    def getFilename(self) -> Optional[str]:
        """对应 ``getFilename()``。"""
        return Path(self.path).name if self.path else None

    def getPath(self) -> str:
        """对应 ``getPath()``。"""
        return self.path

    # ------------------------------------------------------------------ 读取
    def getInputStream(self) -> InputStream:
        """对应 ``getInputStream()``；文件不存在抛 FileNotFoundError。"""
        if self._file is None:
            raise FileNotFoundError("classpath 资源不存在: " + self.path)
        with open(self._file, "rb") as handle:
            return InputStream(handle.read())

    def __repr__(self) -> str:
        return "ClassPathResource(path=%r, file=%r)" % (self.path, self._file)
