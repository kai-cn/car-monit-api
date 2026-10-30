# -*- coding: utf-8 -*-
"""com.ruoyi.common.core.page.PageDomain

源文件：pro-base-common/src/main/java/com/ruoyi/common/core/page/PageDomain.java
"""
from __future__ import annotations

from typing import Optional

from com.ruoyi.common.utils.StringUtils import StringUtils


class PageDomain:
    """分页数据。

    【Java→Python】
    1) 手写 getter/setter → 属性 + 同名方法（保留 setter 是因为 setIsAsc 内部有转换逻辑，
       不能简单用属性赋值替代）。
    2) `private String isAsc = "asc"` 是字段初始化；Python 在 __init__ 中赋默认值。
    3) getOrderBy() 依赖 StringUtils.toUnderScoreCase，属动态计算属性，不能改成字段。
    """

    def __init__(
        self,
        page_num: Optional[int] = None,
        page_size: Optional[int] = None,
        order_by_column: Optional[str] = None,
        is_asc: str = "asc",
        reasonable: Optional[bool] = True,
    ) -> None:
        self.page_num = page_num                      # 当前记录起始索引
        self.page_size = page_size                    # 每页显示记录数
        self.order_by_column = order_by_column        # 排序列
        self.is_asc = is_asc                          # 排序的方向 desc 或者 asc
        self.reasonable = reasonable                  # 分页参数合理化

    def getOrderBy(self) -> str:
        # Java: if (StringUtils.isEmpty(orderByColumn)) return "";
        if StringUtils.isEmpty(self.order_by_column):
            return ""
        # Java: StringUtils.toUnderScoreCase(orderByColumn) + " " + isAsc
        return StringUtils.toUnderScoreCase(self.order_by_column) + " " + str(self.is_asc)

    def getPageNum(self) -> Optional[int]:
        return self.page_num

    def setPageNum(self, page_num: Optional[int]) -> None:
        self.page_num = page_num

    def getPageSize(self) -> Optional[int]:
        return self.page_size

    def setPageSize(self, page_size: Optional[int]) -> None:
        self.page_size = page_size

    def getOrderByColumn(self) -> Optional[str]:
        return self.order_by_column

    def setOrderByColumn(self, order_by_column: Optional[str]) -> None:
        self.order_by_column = order_by_column

    def getIsAsc(self) -> str:
        return self.is_asc

    def setIsAsc(self, is_asc: Optional[str]) -> None:
        # 【Java→Python】Java 的 setter 参数与字段同名，并做前端排序类型兼容；
        # Python 无同名冲突问题，逻辑逐行照搬。
        if StringUtils.isNotEmpty(is_asc):
            if "ascending" == is_asc:
                is_asc = "asc"
            elif "descending" == is_asc:
                is_asc = "desc"
            self.is_asc = is_asc

    def getReasonable(self) -> bool:
        # Java: if (StringUtils.isNull(reasonable)) return Boolean.TRUE;
        if StringUtils.isNull(self.reasonable):
            return True
        return bool(self.reasonable)

    def setReasonable(self, reasonable: Optional[bool]) -> None:
        self.reasonable = reasonable
