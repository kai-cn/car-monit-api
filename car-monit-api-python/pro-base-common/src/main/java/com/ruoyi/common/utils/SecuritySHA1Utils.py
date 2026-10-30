# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.SecuritySHA1Utils

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/SecuritySHA1Utils.java
"""
from __future__ import annotations

import hashlib


class SecuritySHA1Utils:
    """SHA1 工具。

    【Java→Python】
    1) MessageDigest.getInstance("SHA") → hashlib.sha1（"SHA" 与 "SHA-1" 是同一算法）。
    2) Java 的 `((int) b) & 0xff` + `Integer.toHexString` 手工拼十六进制 →
       Python 用 bytes.hex()，结果等价（小写、两位补零）。
    3) Java 方法声明 `throws Exception`（受检异常）→ Python 无受检异常，
       调用点不需要 try/except 包裹（但保持原 try 结构以便逐行对照）。
    4) Java 中 MessageDigest 获取失败会 `e.printStackTrace()` 并返回 ""；
       Python 的 hashlib.sha1 不会失败，故该分支退化为不可达。
    """

    @staticmethod
    def shaEncode(in_str: str) -> str:
        try:
            sha = hashlib.sha1()
        except Exception as e:  # pragma: no cover - 与 Java 的防御性分支对应
            print(str(e))
            return ""
        byte_array = in_str.encode("utf-8")
        # 【Java→Python】`MessageDigest#digest(byte[])` 一步返回摘要字节 → 对应
        # `hashlib.sha1(data).digest()`；此处等价地直接取 `hexdigest()`（小写 40 位）。
        # 注意：旧写法 `sha.digest(byte_array)` 是 Python 没有的签名（会抛 TypeError）。
        return hashlib.sha1(byte_array).hexdigest()
