# -*- coding: utf-8 -*-
"""com.ruoyi.common.constant.GenConstants

源文件：pro-base-common/src/main/java/com/ruoyi/common/constant/GenConstants.java
"""


class GenConstants:
    """代码生成通用常量。

    【Java→Python】String[] 常量用 list 表达，保留 Java 数组“元素可写”的语义。
    """

    # ---- 模板类型
    TPL_CRUD = "crud"
    TPL_TREE = "tree"
    TPL_SUB = "sub"

    # ---- 树表字段
    TREE_CODE = "treeCode"
    TREE_PARENT_CODE = "treeParentCode"
    TREE_NAME = "treeName"
    PARENT_MENU_ID = "parentMenuId"
    PARENT_MENU_NAME = "parentMenuName"

    # ---- 数据库字段类型
    COLUMNTYPE_STR = ["char", "varchar", "nvarchar", "varchar2"]
    COLUMNTYPE_TEXT = ["tinytext", "text", "mediumtext", "longtext"]
    COLUMNTYPE_TIME = ["datetime", "time", "date", "timestamp"]
    COLUMNTYPE_NUMBER = [
        "tinyint", "smallint", "mediumint", "int", "number", "integer",
        "bit", "bigint", "float", "double", "decimal",
    ]

    # ---- 页面隐藏字段
    COLUMNNAME_NOT_EDIT = ["id", "create_by", "create_time", "del_flag"]
    COLUMNNAME_NOT_LIST = ["id", "create_by", "create_time", "del_flag", "update_by", "update_time"]
    COLUMNNAME_NOT_QUERY = [
        "id", "create_by", "create_time", "del_flag", "update_by", "update_time", "remark",
    ]

    # ---- 基类字段
    BASE_ENTITY = ["createBy", "createTime", "updateBy", "updateTime", "remark"]
    TREE_ENTITY = ["parentName", "parentId", "orderNum", "ancestors", "children"]

    # ---- HTML 控件
    HTML_INPUT = "input"
    HTML_TEXTAREA = "textarea"
    HTML_SELECT = "select"
    HTML_RADIO = "radio"
    HTML_CHECKBOX = "checkbox"
    HTML_DATETIME = "datetime"
    HTML_IMAGE_UPLOAD = "imageUpload"
    HTML_FILE_UPLOAD = "fileUpload"
    HTML_EDITOR = "editor"

    # ---- Java 类型名
    TYPE_STRING = "String"
    TYPE_INTEGER = "Integer"
    TYPE_LONG = "Long"
    TYPE_DOUBLE = "Double"
    TYPE_BIGDECIMAL = "BigDecimal"
    TYPE_DATE = "Date"

    # ---- 查询方式
    QUERY_LIKE = "LIKE"
    QUERY_EQ = "EQ"

    # ---- 必填
    REQUIRE = "1"
