# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.text.Convert

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/text/Convert.java
"""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_EVEN
from enum import Enum
from typing import Any, Iterable, Optional, Type

from com.ruoyi.common.core.text.CharsetKit import CharsetKit
from com.ruoyi.common.utils.StringUtils import StringUtils


# =============================================================================
# 【Java→Python】Java 数值类型与 Python 的差异辅助函数
# =============================================================================
def _java_split(pattern: str, text: str) -> list[str]:
    """等价于 Java 的 ``text.split(pattern)``（默认 limit=0）。

    差异有两点，都会影响业务结果，必须显式还原：
    1) Java 的 split 参数是**正则表达式**，不是字面量 → 用 re.split；
    2) Java 会**丢弃尾部空字符串**，Python 的 re.split/str.split 会保留
       （"a,,b,," → Java ["a","","b"]，Python ["a","","b","",""]）。
    """
    parts = re.split(pattern, text)
    end = len(parts)
    while end > 0 and parts[end - 1] == "":
        end -= 1
    return parts[:end]


def _java_byte(value: int) -> int:
    """Number.byteValue()：截断为有符号 8 位（Python int 无位宽，需手工模拟）。"""
    value &= 0xFF
    return value - 0x100 if value >= 0x80 else value


def _java_short(value: int) -> int:
    """Number.shortValue()：截断为有符号 16 位。"""
    value &= 0xFFFF
    return value - 0x10000 if value >= 0x8000 else value


def _java_int(value: int) -> int:
    """Number.intValue()：截断为有符号 32 位。"""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value >= 0x80000000 else value


class Convert:
    """类型转换器。

    【Java→Python】总体差异：
    1) Java 的 Byte/Short/Integer/Long/Float/Double 是带位宽的包装类型，Python 只有 int/float；
       凡是 Java 通过 Number.xxxValue() 做**截断**的地方，这里用 _java_byte/_java_short/_java_int 还原。
    2) 重载方法（toStr(Object) 与 toStr(Object,String) 等）→ Python 用默认参数表达。
    3) Java 的 String.split 是正则 + 丢弃尾部空串 → 统一走 _java_split。
    4) BigInteger 在 Python 中就是 int（无上限），因此 toBigInteger 退化为 int 转换。
    5) java.nio.ByteBuffer → Python 用 bytes/bytearray/memoryview 表达。
    """

    # ------------------------------------------------------------------ toStr
    @staticmethod
    def toStr(value: Any, default_value: Optional[str] = None) -> Optional[str]:
        if value is None:
            return default_value
        if isinstance(value, str):
            return value
        # 【Java→Python】Java 的 value.toString() 对 boolean 得 "true"/"false"，
        # Python 的 str(True) 得 "True"；为保持拼接/落库结果一致，这里做小写化转换。
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    # ----------------------------------------------------------------- toChar
    @staticmethod
    def toChar(value: Any, default_value: Optional[str] = None) -> Optional[str]:
        """Java 的 Character 是单个 UTF-16 码元；Python 用长度 1 的 str 表达。"""
        if value is None:
            return default_value
        if isinstance(value, str) and len(value) == 1:
            return value
        value_str = Convert.toStr(value, None)
        return default_value if StringUtils.isEmpty(value_str) else value_str[0]

    # ----------------------------------------------------------------- toByte
    @staticmethod
    def toByte(value: Any, default_value: Optional[int] = None) -> Optional[int]:
        if value is None:
            return default_value
        if isinstance(value, int) and not isinstance(value, bool):
            return _java_byte(value)
        if isinstance(value, (int, float)):
            return _java_byte(int(value))
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        try:
            parsed = int(value_str)
            # Java: Byte.parseByte 超出 -128..127 会抛 NumberFormatException
            if parsed < -128 or parsed > 127:
                return default_value
            return parsed
        except Exception:
            return default_value

    # ---------------------------------------------------------------- toShort
    @staticmethod
    def toShort(value: Any, default_value: Optional[int] = None) -> Optional[int]:
        if value is None:
            return default_value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return _java_short(int(value))
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        try:
            parsed = int(value_str.strip())
            if parsed < -32768 or parsed > 32767:
                return default_value
            return parsed
        except Exception:
            return default_value

    # --------------------------------------------------------------- toNumber
    @staticmethod
    def toNumber(value: Any, default_value: Any = None) -> Any:
        if value is None:
            return default_value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        try:
            # 【Java→Python】NumberFormat.getInstance() 是“按当前 Locale 解析”，
            # 会接受千分位（"1,234"→1234）；Python 无对应实现，这里先去掉逗号再解析。
            cleaned = value_str.replace(",", "")
            return int(cleaned) if re.fullmatch(r"[+-]?\d+", cleaned) else float(cleaned)
        except Exception:
            return default_value

    # ------------------------------------------------------------------ toInt
    @staticmethod
    def toInt(value: Any, default_value: Optional[int] = None) -> Optional[int]:
        if value is None:
            return default_value
        if isinstance(value, bool):
            # Java 的 Boolean 不是 Number，会走字符串分支："true" 解析失败 → 默认值
            value_str = Convert.toStr(value, None)
            try:
                return int(value_str.strip())
            except Exception:
                return default_value
        if isinstance(value, (int, float)):
            return _java_int(int(value))
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        try:
            return int(value_str.strip())
        except Exception:
            return default_value

    # -------------------------------------------------------------- 数组转换
    @staticmethod
    def toIntArray(str_value: str, split: str = ",") -> list[int]:
        """Java: toIntArray(String) / toIntArray(String split, String str)。

        【Java→Python】参数顺序在 Java 中是 (split, str)，而单参重载是 (str)；
        Python 合并后把 str 放在第一位、split 作为关键字默认值，避免调用点歧义。
        """
        if StringUtils.isEmpty(str_value):
            return []
        arr = _java_split(split, str_value)
        return [Convert.toInt(item, 0) for item in arr]

    @staticmethod
    def toLongArray(str_value: str, split: str = ",") -> list[Optional[int]]:
        if StringUtils.isEmpty(str_value):
            return []
        arr = _java_split(split, str_value)
        return [Convert.toLong(item, None) for item in arr]

    @staticmethod
    def toStrArray(str_value: str, split: str = ",") -> list[str]:
        # Java: return str.split(split); —— 正则 + 丢弃尾部空串
        return _java_split(split, str_value)

    # ----------------------------------------------------------------- toLong
    @staticmethod
    def toLong(value: Any, default_value: Optional[int] = None) -> Optional[int]:
        if value is None:
            return default_value
        if isinstance(value, bool):
            value_str = Convert.toStr(value, None)
            try:
                return int(value_str.strip())
            except Exception:
                return default_value
        if isinstance(value, (int, float)):
            return int(value)
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        try:
            # 支持科学计数法（Java: new BigDecimal(valueStr.trim()).longValue()）
            # 【Java→Python】BigDecimal.longValue() 是向零截断，int(Decimal) 同样是向零截断。
            return int(Decimal(value_str.strip()))
        except Exception:
            return default_value

    # --------------------------------------------------------------- toDouble
    @staticmethod
    def toDouble(value: Any, default_value: Optional[float] = None) -> Optional[float]:
        if value is None:
            return default_value
        if isinstance(value, bool):
            return default_value
        if isinstance(value, (int, float)):
            return float(value)
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        try:
            return float(Decimal(value_str.strip()))
        except Exception:
            return default_value

    # ---------------------------------------------------------------- toFloat
    @staticmethod
    def toFloat(value: Any, default_value: Optional[float] = None) -> Optional[float]:
        # 【Java→Python】Java 的 Float 只有 7 位有效数字；Python 的 float 是双精度。
        # 若需严格模拟 float32，可用 struct.unpack("f", struct.pack("f", x))[0]；
        # 本项目未用于精度敏感场景，故保持 Python 双精度并在调用点注明。
        return Convert.toDouble(value, default_value)

    # ----------------------------------------------------------------- toBool
    @staticmethod
    def toBool(value: Any, default_value: Optional[bool] = None) -> Optional[bool]:
        if value is None:
            return default_value
        if isinstance(value, bool):
            return value
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        value_str = value_str.strip().lower()
        if value_str in ("true", "yes", "ok", "1"):
            return True
        if value_str in ("false", "no", "0"):
            return False
        return default_value

    # 兼容 Java 中的另一个方法名 toBoolean（若存在调用点）
    toBoolean = toBool

    # ----------------------------------------------------------------- toEnum
    @staticmethod
    def toEnum(clazz: Type[Enum], value: Any, default_value: Optional[Enum] = None) -> Optional[Enum]:
        if value is None:
            return default_value
        if isinstance(value, clazz):
            return value
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        try:
            # Java: Enum.valueOf(clazz, valueStr) 要求精确匹配枚举常量名
            return clazz[value_str]
        except Exception:
            return default_value

    # ------------------------------------------------------------ toBigInteger
    @staticmethod
    def toBigInteger(value: Any, default_value: Optional[int] = None) -> Optional[int]:
        """【Java→Python】Python 的 int 本身就是任意精度，等价于 BigInteger。"""
        if value is None:
            return default_value
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        try:
            return int(value_str)
        except Exception:
            return default_value

    # ----------------------------------------------------------- toBigDecimal
    @staticmethod
    def toBigDecimal(value: Any, default_value: Optional[Decimal] = None) -> Optional[Decimal]:
        if value is None:
            return default_value
        if isinstance(value, Decimal):
            return value
        if isinstance(value, bool):
            return default_value
        if isinstance(value, int):
            return Decimal(value)
        if isinstance(value, float):
            # 【Java→Python】Java 这里用的是 BigDecimal.valueOf(double)，即按
            # Double.toString 的最短十进制表示构造；Python 的 Decimal(str(float)) 语义相同
            #（若用 Decimal(float) 会得到二进制精确值，结果会不同）。
            return Decimal(str(value))
        value_str = Convert.toStr(value, None)
        if StringUtils.isEmpty(value_str):
            return default_value
        try:
            return Decimal(value_str)
        except Exception:
            return default_value

    # ---------------------------------------------------------------- str 系列
    @staticmethod
    def utf8Str(obj: Any) -> Optional[str]:
        return Convert.str_of(obj, CharsetKit.CHARSET_UTF_8)

    @staticmethod
    def str_of(obj: Any, charset: Optional[str] = None) -> Optional[str]:
        """对应 str(Object, String) / str(Object, Charset) / str(byte[], ...) 等重载。"""
        if obj is None:
            return None
        if isinstance(obj, str):
            return obj
        if isinstance(obj, (bytes, bytearray, memoryview)):
            return Convert.str_bytes(bytes(obj), charset)
        return str(obj)

    @staticmethod
    def str_bytes(data: Optional[bytes], charset: Optional[str] = None) -> Optional[str]:
        if data is None:
            return None
        # Java: new String(data) 用平台默认字符集；Python 侧统一按 utf-8 兜底
        return data.decode(charset or "utf-8", errors="replace")

    # Java 中的方法名就是 str(...)，Python 用 str_of + 别名保持调用点一致
    str = str_of

    # ------------------------------------------------------------ 全角/半角
    @staticmethod
    def toSBC(input_text: str, not_convert_set: Optional[Iterable[str]] = None) -> str:
        """半角转全角。"""
        chars = list(input_text)
        for i, ch in enumerate(chars):
            if not_convert_set is not None and ch in not_convert_set:
                continue
            if ch == " ":
                chars[i] = "\u3000"
            elif ord(ch) < 0o177:
                # 【Java→Python】Java 的 char 是 16 位无符号整数，可做算术；
                # Python 的字符需用 ord/chr 转换。
                chars[i] = chr(ord(ch) + 65248)
        return "".join(chars)

    @staticmethod
    def toDBC(text: str, not_convert_set: Optional[Iterable[str]] = None) -> str:
        """全角转半角。"""
        chars = list(text)
        for i, ch in enumerate(chars):
            if not_convert_set is not None and ch in not_convert_set:
                continue
            if ch == "\u3000":
                chars[i] = " "
            elif 0xFF00 < ord(ch) < 0xFF5F:
                chars[i] = chr(ord(ch) - 65248)
        return "".join(chars)

    # --------------------------------------------------------- 数字金额大写
    @staticmethod
    def digitUppercase(n: float) -> str:
        """数字金额大写转换（逐行移植，含原实现的边界行为）。"""
        fraction = ["角", "分"]
        digit = ["零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖"]
        unit = [["元", "万", "亿"], ["", "拾", "佰", "仟"]]

        head = "负" if n < 0 else ""
        n = abs(n)

        s = ""
        for i in range(len(fraction)):
            # 优化 double 计算精度丢失问题
            # 【Java→Python】new BigDecimal(double) 使用二进制精确值，Python 的 Decimal(float)
            # 行为完全相同；若换成 Decimal(str(n)) 会得到不同结果，故保持 Decimal(n)。
            n_num = Decimal(n)
            decimal = Decimal(10)
            scale = (n_num * decimal).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            d = float(scale)
            piece = digit[int((d * (10 ** i)) // 1 % 10)] + fraction[i]
            s += re.sub(r"(零.)+", "", piece)
        if len(s) < 1:
            s = "整"
        integer_part = int(n // 1)

        i = 0
        while i < len(unit[0]) and integer_part > 0:
            p = ""
            j = 0
            while j < len(unit[1]) and n > 0:
                p = digit[integer_part % 10] + unit[1][j] + p
                integer_part = integer_part // 10
                j += 1
            p = re.sub(r"(零.)*零$", "", p)
            p = re.sub(r"^$", "零", p)
            s = p + unit[0][i] + s
            i += 1
        s = re.sub(r"(零.)*零元", "元", s)
        s = re.sub(r"(零.)+", "", s, count=1)
        s = re.sub(r"(零.)+", "零", s)
        s = re.sub(r"^整$", "零元整", s)
        return head + s
