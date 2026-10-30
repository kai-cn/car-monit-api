# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.CryptoJSTools

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/CryptoJSTools.java

【Java→Python】整体说明（本文件是加密相关，差异最需要留意）
1) 算法固定为 **DES / ECB / NoPadding**，密钥为 8 字节 ASCII ``"#1*x3zp_"``。
   Python 标准库没有 DES，这里按以下顺序选择实现：
   a. 若安装了 pycryptodome：``Crypto.Cipher.DES``（最直观，8 字节密钥直接用）；
   b. 否则使用 ``cryptography`` 的 ``TripleDES`` **传入 8 字节密钥**：
      TripleDES 在 K1=K2=K3 时**等价于单 DES**（EDE 退化为单次加密），
      因此密文与 Java 的 DES/ECB/NoPadding 完全一致。
   两条路径都经过 DES 标准测试向量校验（见 ``_self_check``）。
2) ``Cipher.doFinal(...)`` **要求数据长度是 8 的倍数**（NoPadding），否则抛
   IllegalBlockSizeException；Python 侧抛 ValueError 并保留同样的报错语义。
3) **保留原缺陷**：原 Java 用 ``message.length()``（**字符数**）判断补空格，
   但随后 ``message.getBytes(UTF_8)`` 是**字节数**。若消息含中文（UTF-8 下 3 字节），
   字符数补齐到 8 的倍数后字节数往往不是 8 的倍数 → 抛 IllegalBlockSizeException。
   Python 侧保持完全相同的补位逻辑（按字符数补空格），不偷偷修正。
4) 十六进制生成：``Integer.toHexString((item & 0xFF) | 0x100)`` 再取 [1,3) 两个字符，
   等价于 ``f"{b:02x}"``；随后 ``toUpperCase()`` 再按 UTF-8 取字节做 Base64。
5) ``Exception`` 直接向外抛（方法声明 ``throws Exception``）→ Python 不声明受检异常，
   同样直接向上抛；``main`` → ``if __name__ == "__main__":``。
6) ``System.out.println`` → ``print``。
"""
from __future__ import annotations

import base64
from typing import Optional

from com.ruoyi.common.utils.RepeatUtil import RepeatUtil


def _des_ecb_encrypt(key_bytes: bytes, data: bytes) -> bytes:
    """DES/ECB/NoPadding 加密，优先 pycryptodome，其次 cryptography.TripleDES(8字节)。"""
    if len(key_bytes) != 8:
        # Java: new SecretKeySpec(8字节以外, "DES") 在 init 时抛 InvalidKeyException
        raise ValueError("Wrong key size: DES key must be 8 bytes")
    if len(data) % 8 != 0:
        # Cipher.doFinal 对 NoPadding 的约束
        raise ValueError("Input length not multiple of 8 bytes")

    try:
        from Crypto.Cipher import DES as _PyCryptodomeDES  # type: ignore
        return _PyCryptodomeDES.new(key_bytes, _PyCryptodomeDES.MODE_ECB).encrypt(data)
    except ImportError:
        pass

    try:
        # cryptography >= 43 把 TripleDES 移到了 decrepit 模块
        from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
    except ImportError:
        from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES

    from cryptography.hazmat.primitives.ciphers import Cipher, modes

    # 8 字节密钥时 K1=K2=K3，EDE 等价于单次 DES 加密
    cipher = Cipher(TripleDES(key_bytes), modes.ECB())
    encryptor = cipher.encryptor()
    return encryptor.update(data) + encryptor.finalize()


def _self_check() -> bool:
    """用 DES 标准测试向量校验实现（key=0123456789ABCDEF, pt="Now is t"）。

    期望密文：3FA40E8A984D4815
    """
    key = bytes.fromhex("0123456789ABCDEF")
    plain = b"Now is t"
    encrypted = _des_ecb_encrypt(key, plain)
    return encrypted.hex().upper() == "3FA40E8A984D4815"


class CryptoJSTools:
    """等价前端 CryptoJS 加密。"""

    # 注意：密钥应该足够长且随机
    key = "#1*x3zp_"

    @staticmethod
    def encryptDES(message: Optional[str]) -> str:
        length = len(message)
        if length % 8 != 0:
            # 【Java→Python】原样保留：按“字符数”补空格（见文件头第 3 点缺陷说明）
            message += RepeatUtil.repeat(" ", 8 - length % 8)

        secret_key_spec = CryptoJSTools.key.encode("UTF-8")
        encrypted_bytes = _des_ecb_encrypt(secret_key_spec, message.encode("UTF-8"))

        sb: list[str] = []
        for item in encrypted_bytes:
            # Integer.toHexString((item & 0xFF) | 0x100).substring(1, 3)
            sb.append(f"{item:02x}")
        encrypted = base64.b64encode("".join(sb).upper().encode("UTF-8")).decode("ascii")
        print("encrypted===" + encrypted)
        return encrypted


# https://api.m.jd.com/client.action?functionId=halleyOrderDetail&appid=customerAssistant&...（原注释链接）
if __name__ == "__main__":
    try:
        CryptoJSTools.encryptDES("jd_52c00cd62db8c")
    except Exception:
        import traceback
        traceback.print_exc()
