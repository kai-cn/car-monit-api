# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.MD5Example

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/MD5Example.java

【Java→Python】整体说明
1) ``MessageDigest.getInstance("MD5")`` → ``hashlib.md5()``；
   ``digest()`` 返回 16 字节 → ``digest()`` 同样返回 bytes。
2) ``String.format("%02x", b)`` 对 Java 的 **有符号 byte** 会按无符号补码格式化
   （如 -1 → "ff"）；Python 的 ``f"{b:02x}"`` 用无符号字节，结果完全一致。
3) **重要差异**：Java 的 ``originalString.getBytes()`` 使用**平台默认字符集**
   （``file.encoding``，Windows 中文环境常为 GBK，Linux 容器多为 UTF-8），
   同一个字符串在不同机器上 MD5 可能不同。Python 统一显式使用 UTF-8，
   并把字符集做成参数 ``charset``，便于在需要与旧 Java 结果对齐时传入 "GBK"。
4) ``NoSuchAlgorithmException`` → Python 的 hashlib 必然支持 md5，
   这里保留 try/except 并返回 None，与 Java 的 catch 分支一致。
5) ``Base64.getEncoder().encodeToString(bytes)`` → ``base64.b64encode(...).decode()``
   （Java 标准 Base64 无换行，与 b64encode 一致）。
6) ``main`` → ``if __name__ == "__main__":``。
"""
from __future__ import annotations

import base64
import hashlib
import urllib.parse
from typing import Optional


class MD5Example:

    @staticmethod
    def toMD5(originalString: str, charset: str = "UTF-8") -> Optional[str]:
        """对字符串求 MD5（32 位小写十六进制）。"""
        try:
            # Java: MessageDigest.getInstance("MD5"); md.update(str.getBytes());
            digest = hashlib.md5(originalString.encode(charset)).digest()
            sb: list[str] = []
            for b in digest:
                # Java: String.format("%02x", b)
                sb.append(f"{b:02x}")
            return "".join(sb)
        except (ValueError, LookupError):
            # Java: catch (NoSuchAlgorithmException e) { e.printStackTrace(); return null; }
            import traceback
            traceback.print_exc()
            return None


if __name__ == "__main__":
    data = '{"ShipperCode": "STO","LogisticCode": "773279402851605"}'
    key = "4597fcc9-e48b-4d40-832a-b795cc3338bc"

    originalString = data + key
    md5Hash = MD5Example.toMD5(originalString)
    print("MD5 Hash: " + str(md5Hash))

    # Java: md5Hash.getBytes(Charset.forName("UTF-8"))
    encodedString = base64.b64encode(md5Hash.encode("UTF-8")).decode("ascii")
    # String encodedString = Base64.getEncoder().encodeToString(originalString.getBytes());
    print("Encoded String: " + encodedString)

    # Java: URLEncoder.encode(encodedString, "UTF-8") → 空格变 '+'（b64 中不出现，结果等价）
    encodedString2 = urllib.parse.quote_plus(encodedString, encoding="UTF-8")
    # String decodedString2 = Base64.getUrlEncoder().encodeToString(encodedString.getBytes());
    print("Decoded string: " + encodedString2)
