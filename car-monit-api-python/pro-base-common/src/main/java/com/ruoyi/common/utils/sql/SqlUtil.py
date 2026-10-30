# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.sql.SqlUtil

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/sql/SqlUtil.java
"""
from __future__ import annotations

import re
from typing import Optional

from com.ruoyi.common.exception.UtilException import UtilException
from com.ruoyi.common.utils.StringUtils import StringUtils, apache_split


class SqlUtil:
    """sql 操作工具类。

    【Java→Python】
    1) String.matches(regex) 要求整串匹配 → Python 用 re.fullmatch（不是 re.match）。
    2) StringUtils.split(str, "\\|") 来自 Apache commons-lang3：第二参数是**字符集合**
       （即 '\\' 与 '|' 两个字符），不是正则 → 用 apache_split 还原，
       不能用 re.split("\\|")，否则遇到 "and " 这类没有竖线的关键字会切不开。
    3) SQL_PATTERN 中的 "\\ " 是 Java 字符串里的一个空格，正则等价于 [a-zA-Z0-9_ ,.]。
    """

    # 定义常用的 sql 关键字
    SQL_REGEX = (
        "and |extractvalue|updatexml|exec |insert |select |delete |update |drop |count |chr |mid |"
        "master |truncate |char |declare |or |+|user()"
    )

    # 仅支持字母、数字、下划线、空格、逗号、小数点（支持多个字段排序）
    SQL_PATTERN = r"[a-zA-Z0-9_ ,.]+"

    # 限制 orderBy 最大长度
    ORDER_BY_MAX_LENGTH = 500

    @staticmethod
    def escapeOrderBySql(value: Optional[str]) -> Optional[str]:
        """检查字符，防止注入绕过。"""
        if StringUtils.isNotEmpty(value) and not SqlUtil.isValidOrderBySql(value):
            raise UtilException("参数不符合规范，不能进行查询")
        if StringUtils.length(value) > SqlUtil.ORDER_BY_MAX_LENGTH:
            raise UtilException("参数已超过最大限制，不能进行查询")
        return value

    @staticmethod
    def isValidOrderBySql(value: str) -> bool:
        """验证 order by 语法是否符合规范。"""
        return re.fullmatch(SqlUtil.SQL_PATTERN, value) is not None

    @staticmethod
    def filterKeyword(value: Optional[str]) -> None:
        """SQL 关键字检查。"""
        if StringUtils.isEmpty(value):
            return
        sql_keywords = apache_split(SqlUtil.SQL_REGEX, "\\|")
        for sql_keyword in sql_keywords:
            if StringUtils.indexOfIgnoreCase(value, sql_keyword) > -1:
                raise UtilException("参数存在SQL注入风险")
