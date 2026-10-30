# -*- coding: utf-8 -*-
"""com.ruoyi.common.constant.UserConstants

源文件：pro-base-common/src/main/java/com/ruoyi/common/constant/UserConstants.java
"""


class UserConstants:
    """用户常量信息。

    【Java→Python】boolean 常量 UNIQUE / NOT_UNIQUE 保持 True/False；
    Java 的 final static boolean 在 Python 中即类属性。
    """

    SYS_USER = "SYS_USER"           # 平台内系统用户的唯一标志
    NORMAL = "0"                    # 正常状态
    EXCEPTION = "1"                 # 异常状态
    USER_DISABLE = "1"              # 用户封禁状态
    ROLE_DISABLE = "1"              # 角色封禁状态
    DEPT_NORMAL = "0"               # 部门正常状态
    DEPT_DISABLE = "1"              # 部门停用状态
    DICT_NORMAL = "0"               # 字典正常状态
    YES = "Y"                       # 是否为系统默认（是）
    YES_FRAME = "0"                 # 是否菜单外链（是）
    NO_FRAME = "1"                  # 是否菜单外链（否）
    TYPE_DIR = "M"                  # 菜单类型（目录）
    TYPE_MENU = "C"                 # 菜单类型（菜单）
    TYPE_BUTTON = "F"               # 菜单类型（按钮）
    LAYOUT = "Layout"               # Layout组件标识
    PARENT_VIEW = "ParentView"      # ParentView组件标识
    INNER_LINK = "InnerLink"        # InnerLink组件标识

    # 校验是否唯一的返回标识
    UNIQUE = True
    NOT_UNIQUE = False

    # 用户名/密码长度限制
    USERNAME_MIN_LENGTH = 2
    USERNAME_MAX_LENGTH = 20
    PASSWORD_MIN_LENGTH = 5
    PASSWORD_MAX_LENGTH = 20

    # 校验返回结果码
    UNIQUE_OLD = "0"
    NOT_UNIQUE_OLD = "1"

    DEFAULT_PWD = "Sys@cg0624!"
