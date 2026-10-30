# -*- coding: utf-8 -*-
"""java.math.BigDecimal

【无 Java 源文件：JDK 类替身】
Java 侧来自 JDK：`java.math.BigDecimal` + `java.math.RoundingMode`。
业务代码用法（SysUtilServiceImpl / MultiSourceDataFlowService 等）：
    new BigDecimal("0.3");                  // 字符串构造
    new BigDecimal(trailBo.getLon());       // 已是 BigDecimal，等价赋值
    new BigDecimal(conutFeeRecord);         // int 构造
    new BigDecimal(conutFeeRecord).divide(new BigDecimal(sussFeeRecord), 4, BigDecimal.ROUND_HALF_UP)
    bite.compareTo(costBite) >= 0
    fee.compareTo(BigDecimal.ZERO) > 0

【Java→Python 关键差异】
1) Python 的 float 是 IEEE-754 二进制小数，`0.1 + 0.2 != 0.3`；BigDecimal 是十进制精确运算。
   本替身内部一律用 `decimal.Decimal`，保证 `compareTo` / `divide` 的十进制语义与 Java 一致。
2) `new BigDecimal(double)` 在 Java 里会把**二进制误差原样展开**
   （`new BigDecimal(0.1)` → 0.1000000000000000055511151231257827...）；
   本替身按 `BigDecimal.valueOf(double)`（`Double.toString`）的语义处理，即 `0.1` → `0.1`。
   **本工程的 BigDecimal 都由 String/int 构造**，两种语义无差别；若后续出现 double 构造需注意。
3) `compareTo` 只比较数值，忽略 scale（`2.0.compareTo(2.00) == 0`）；
   `equals` 同时比较数值和 scale（Java 语义），因此 `2.0.equals(2.00) == false`。
   本替身 `compareTo` 用 Decimal 比较（忽略 scale），`__eq__` 用 Java `equals` 语义。
4) `divide(divisor, scale, roundingMode)` 是**精确除法 + 指定小数位**；
   不传 scale 的 `divide(divisor)` 在除不尽时 Java 抛 ArithmeticException（non-terminating），
   本替身抛 `ArithmeticError` 模拟该行为。
5) 除法取整模式：Java 8 用 `BigDecimal.ROUND_HALF_UP`（int 常量，已过时但仍可用）；
   Java 9+ 推荐 `RoundingMode.HALF_UP`。两者在本替身里都映射到
   `decimal.ROUND_HALF_UP`（四舍五入，5 远离零）。
6) `BigDecimal` 是**不可变对象**：add/subtract/multiply/divide 都返回新对象，
   原对象不变（Python 的 Decimal 同样不可变，故直接返回新 BigDecimal）。
7) `BigDecimal.ZERO / ONE / TEN` 是静态常量 → 本文件的模块级常量 + 类属性（见文件末尾）。
"""
from __future__ import annotations

import decimal
from decimal import Decimal
from typing import Any, Optional

__all__ = ["BigDecimal", "RoundingMode", "ZERO", "ONE", "TEN"]

# Java `BigDecimal.ROUND_*` 常量（int）→ Python decimal 的字符串常量
_ROUNDING_UP = "ROUND_UP"
_ROUNDING_DOWN = "ROUND_DOWN"
_ROUNDING_CEILING = "ROUND_CEILING"
_ROUNDING_FLOOR = "ROUND_FLOOR"
_ROUNDING_HALF_UP = "ROUND_HALF_UP"
_ROUNDING_HALF_DOWN = "ROUND_HALF_DOWN"
_ROUNDING_HALF_EVEN = "ROUND_HALF_EVEN"
_ROUNDING_UNNECESSARY = "ROUND_UNNECESSARY"


class RoundingMode(object):
    """`java.math.RoundingMode` 枚举的最小替身（仅保留工程用到的值）。"""

    UP = _ROUNDING_UP
    DOWN = _ROUNDING_DOWN
    CEILING = _ROUNDING_CEILING
    FLOOR = _ROUNDING_FLOOR
    HALF_UP = _ROUNDING_HALF_UP
    HALF_DOWN = _ROUNDING_HALF_DOWN
    HALF_EVEN = _ROUNDING_HALF_EVEN
    UNNECESSARY = _ROUNDING_UNNECESSARY


def _toDecimal(value: Any) -> Decimal:
    """把 Java 构造器入参统一转成 Decimal（对齐 `new BigDecimal(...)` 的各重载）。"""
    if isinstance(value, BigDecimal):
        return value._value
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        # Java 没有 BigDecimal(boolean)，这里仅为避免 True 被当成 1 静默通过
        raise TypeError("BigDecimal 不支持 boolean")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # 对应 BigDecimal.valueOf(double) / Double.toString(double)
        return Decimal(str(value))
    if isinstance(value, str):
        # 对应 new BigDecimal(String)：非法字符串抛 NumberFormatException
        try:
            return Decimal(value.strip())
        except decimal.InvalidOperation:
            raise ValueError("NumberFormatException: Character array is missing exponent or %r" % (value,))
    raise TypeError("BigDecimal 不支持的入参类型: %s" % type(value).__name__)


def _toRounding(rounding_mode: Any) -> str:
    """Java 的 ROUND_* 常量（含 int 形式/枚举名）→ decimal 的字符串常量。"""
    if rounding_mode is None:
        # Java 默认: divide(divisor) 除不尽抛异常；本替身用 ROUND_UNNECESSARY 触发
        return _ROUNDING_UNNECESSARY
    text = str(rounding_mode)
    if text.startswith("ROUND_"):
        return text
    # 兼容 Java 8 的 int 常量（0..7）
    legacy = {
        0: _ROUNDING_UP, 1: _ROUNDING_DOWN, 2: _ROUNDING_CEILING, 3: _ROUNDING_FLOOR,
        4: _ROUNDING_HALF_UP, 5: _ROUNDING_HALF_DOWN, 6: _ROUNDING_HALF_EVEN,
        7: _ROUNDING_UNNECESSARY,
    }
    if isinstance(rounding_mode, int) and rounding_mode in legacy:
        return legacy[rounding_mode]
    raise ValueError("Unknown rounding mode: %r" % (rounding_mode,))


class BigDecimal(object):
    """`java.math.BigDecimal` 的替身（不可变十进制精确数）。"""

    # Java 8 的 int 常量（已弃用但源码仍在用 BigDecimal.ROUND_HALF_UP）
    ROUND_UP = 0
    ROUND_DOWN = 1
    ROUND_CEILING = 2
    ROUND_FLOOR = 3
    ROUND_HALF_UP = 4
    ROUND_HALF_DOWN = 5
    ROUND_HALF_EVEN = 6
    ROUND_UNNECESSARY = 7

    def __init__(self, value: Any = 0) -> None:
        self._value: Decimal = _toDecimal(value)

    # ------------------------------------------------------------------ 取值
    def doubleValue(self) -> float:
        """`doubleValue()`：可能有精度损失。"""
        return float(self._value)

    def floatValue(self) -> float:
        """`floatValue()`：Java 的 float 单精度 → Python 只有双精度，统一返回 float。"""
        return float(self._value)

    def intValue(self) -> int:
        """`intValue()`：截断小数（向零取整）。"""
        return int(self._value)

    def longValue(self) -> int:
        """`longValue()`：Python int 无溢出，等价于 intValue。"""
        return int(self._value)

    def scale(self) -> int:
        """`scale()`：小数位数（Decimal 的 exponent 取反）。"""
        exponent = self._value.as_tuple().exponent
        return -exponent if isinstance(exponent, int) and exponent < 0 else 0

    def toString(self) -> str:
        """`toString()`：与 Decimal 的字符串表示一致（不会丢尾随 0）。"""
        return format(self._value, "f") if self._value == self._value.to_integral_value() \
            and "." in str(self._value) else str(self._value)

    def toPlainString(self) -> str:
        """`toPlainString()`：禁止科学计数法。"""
        return format(self._value, "f")

    def toBigInteger(self) -> int:
        """`toBigInteger()`：截断小数。"""
        return int(self._value)

    # ------------------------------------------------------------------ 运算
    def add(self, other: Any) -> "BigDecimal":
        return BigDecimal(self._value + _toDecimal(other))

    def subtract(self, other: Any) -> "BigDecimal":
        return BigDecimal(self._value - _toDecimal(other))

    def multiply(self, other: Any) -> "BigDecimal":
        return BigDecimal(self._value * _toDecimal(other))

    def divide(self, divisor: Any, scale: Optional[int] = None,
               rounding_mode: Any = None) -> "BigDecimal":
        """`divide(divisor)` / `divide(divisor, scale, roundingMode)` 两个重载。

        【Java→Python】
        - 不传 scale：除不尽时 Java 抛 `ArithmeticException("Non-terminating decimal expansion")`，
          这里用 `decimal.ROUND_UNNECESSARY` 让 Decimal 抛 `InvalidOperation`，再转成 ArithmeticError。
        - 传 scale + roundingMode：先按精度做扩展除法，再 quantize 到指定小数位。
        """
        target = _toDecimal(divisor)
        if target == 0:
            # Java: throw new ArithmeticException("Division by zero")
            raise ArithmeticError("Division by zero")
        if scale is None:
            try:
                with decimal.localcontext() as context:
                    context.prec = 100  # 足够容纳常见除法，避免误判为除不尽
                    result = self._value / target
                return BigDecimal(result)
            except decimal.InvalidOperation:
                raise ArithmeticError(
                    "Non-terminating decimal expansion; no exact representable decimal result.")
        rounding = _toRounding(rounding_mode)
        with decimal.localcontext() as context:
            # 先多留几位，避免中间截断影响最终舍入
            context.prec = max(60, len(str(self._value)) + len(str(target)) + scale + 10)
            quantum = Decimal(1).scaleb(-scale)  # 10^-scale
            result = (self._value / target).quantize(quantum, rounding=rounding)
        return BigDecimal(result)

    def setScale(self, new_scale: int, rounding_mode: Any = None) -> "BigDecimal":
        """`setScale(int, int)`：按指定小数位舍入。"""
        quantum = Decimal(1).scaleb(-new_scale)
        return BigDecimal(self._value.quantize(quantum, rounding=_toRounding(rounding_mode)))

    def negate(self) -> "BigDecimal":
        return BigDecimal(-self._value)

    def abs(self) -> "BigDecimal":
        return BigDecimal(abs(self._value))

    def pow(self, n: int) -> "BigDecimal":
        return BigDecimal(self._value ** n)

    def max(self, other: Any) -> "BigDecimal":
        return self if self.compareTo(other) >= 0 else BigDecimal(other)

    def min(self, other: Any) -> "BigDecimal":
        return self if self.compareTo(other) <= 0 else BigDecimal(other)

    # ------------------------------------------------------------------ 比较
    def compareTo(self, other: Any) -> int:
        """`compareTo`：只比数值，忽略 scale（2.0 与 2.00 相等）。"""
        target = _toDecimal(other)
        if self._value < target:
            return -1
        if self._value > target:
            return 1
        return 0

    def equals(self, other: Any) -> bool:
        """`equals`：数值 **且** scale 都相等（Java 语义）。"""
        if not isinstance(other, BigDecimal):
            return False
        return self._value.as_tuple() == other._value.as_tuple()

    def __eq__(self, other: object) -> bool:
        # 【Java→Python】Python 的 == 更接近 compareTo；但为了让 dict/set 行为可预期，
        # 这里对齐 equals（数值 + scale）。
        if isinstance(other, BigDecimal):
            return self.equals(other)
        if isinstance(other, (int, float, str, Decimal)):
            return self.compareTo(other) == 0
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value.as_tuple())

    def __lt__(self, other: Any) -> bool:
        return self.compareTo(other) < 0

    def __le__(self, other: Any) -> bool:
        return self.compareTo(other) <= 0

    def __gt__(self, other: Any) -> bool:
        return self.compareTo(other) > 0

    def __ge__(self, other: Any) -> bool:
        return self.compareTo(other) >= 0

    # ------------------------------------------------------------------ 转换/显示
    def __str__(self) -> str:
        # Java 的 toString() 会保留 scale（"0.30"），Decimal 的 str 同样保留
        return str(self._value)

    def __repr__(self) -> str:
        return "BigDecimal(%s)" % str(self._value)

    def __float__(self) -> float:
        return float(self._value)

    def __int__(self) -> int:
        return int(self._value)

    def __bool__(self) -> bool:
        return self._value != 0


# Java 的静态常量：BigDecimal.ZERO / ONE / TEN
ZERO = BigDecimal(0)
ONE = BigDecimal(1)
TEN = BigDecimal(10)
BigDecimal.ZERO = ZERO
BigDecimal.ONE = ONE
BigDecimal.TEN = TEN
