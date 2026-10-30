# -*- coding: utf-8 -*-
"""com.ruoyi.common.annotation.Excel

源文件：pro-base-common/src/main/java/com/ruoyi/common/annotation/Excel.java
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Type(Enum):
    """Excel.Type：字段类型（0：导出导入；1：仅导出；2：仅导入）。"""

    ALL = 0
    EXPORT = 1
    IMPORT = 2

    def value_(self) -> int:
        # Java 枚举里方法名就是 value()；Python 的 Enum 已占用 .value 属性，
        # 因此方法名加下划线，语义完全一致。
        return self.value


class ColumnType(Enum):
    """Excel.ColumnType：导出类型（0数字 1字符串 2图片 3文本）。"""

    NUMERIC = 0
    STRING = 1
    IMAGE = 2
    TEXT = 3

    def value_(self) -> int:
        return self.value


@dataclass
class Excel:
    """自定义导出 Excel 数据注解。

    【Java→Python】Java 的 @interface + 反射是编译期/运行期元数据机制，Python 3.12 没有等价
    的“字段注解带默认值 + 反射读取注解属性”体系（dataclasses 只保留类型，不留默认值对象）。
    这里用 @dataclass 生成一个“注解描述对象”，导出逻辑通过
    ``dataclasses.fields(cls)[i].metadata`` 或直接把 Excel() 实例挂在字段默认值上来读取，
    属性名与 Java 注解成员一一对应。使用时语义等价于：

        @Excel(name="车牌号", cellType=ColumnType.STRING)
        private String platenumber;

    →
        platenumber: str = field(default=None, metadata={"excel": Excel(name="车牌号", ...)})
    """

    sort: int = sys.maxsize                    # 导出时在 excel 中排序（Java Integer.MAX_VALUE）
    name: str = ""                             # 导出到 Excel 中的名字
    date_format: str = ""                      # 日期格式，如 yyyy-MM-dd（Java dateFormat）
    dict_type: str = ""                        # 字典 type（Java dictType）
    read_converter_exp: str = ""               # 读取内容转表达式（Java readConverterExp）
    separator: str = ","                       # 分隔符
    scale: int = -1                            # BigDecimal 精度，-1 表示不开启格式化
    rounding_mode: int = 6                     # BigDecimal 舍入规则，默认 ROUND_HALF_EVEN=6
    height: float = 14                         # 列高
    width: float = 16                          # 列宽
    suffix: str = ""                           # 文字后缀
    default_value: str = ""                    # 空值默认值
    prompt: str = ""                           # 提示信息
    combo: list[str] = field(default_factory=list)      # 只能选择不能输入的内容
    need_merge: bool = False                   # 是否需要纵向合并单元格
    is_export: bool = True                     # 是否导出数据
    target_attr: str = ""                      # 另一个类中的属性名称（支持多级，以小数点隔开）
    is_statistics: bool = False                # 是否自动统计数据
    cell_type: ColumnType = ColumnType.STRING  # 导出类型
    args: list[str] = field(default_factory=list)       # 自定义数据处理器参数
    type: Type = Type.ALL                      # 字段类型

    # Java 注解成员的驼峰命名在 Python 中改为蛇形；保留驼峰别名访问以方便逐行对照。
    @property
    def dateFormat(self) -> str:
        return self.date_format

    @property
    def dictType(self) -> str:
        return self.dict_type

    @property
    def readConverterExp(self) -> str:
        return self.read_converter_exp

    @property
    def roundingMode(self) -> int:
        return self.rounding_mode

    @property
    def defaultValue(self) -> str:
        return self.default_value

    @property
    def needMerge(self) -> bool:
        return self.need_merge

    @property
    def isExport(self) -> bool:
        return self.is_export

    @property
    def targetAttr(self) -> str:
        return self.target_attr

    @property
    def isStatistics(self) -> bool:
        return self.is_statistics

    @property
    def cellType(self) -> ColumnType:
        return self.cell_type


def excel_meta(excel: Excel) -> dict[str, Any]:
    """等价于 Java 反射 getAnnotation(Excel.class)：从字段 metadata 中取出注解对象。"""
    return {"excel": excel}


def get_excel(field_metadata: Optional[dict]) -> Optional[Excel]:
    """等价于 field.getAnnotation(Excel.class)；没有注解时返回 null（None）。"""
    return (field_metadata or {}).get("excel")
