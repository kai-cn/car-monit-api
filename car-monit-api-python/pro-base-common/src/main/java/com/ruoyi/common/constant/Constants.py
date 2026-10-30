# -*- coding: utf-8 -*-
"""com.ruoyi.common.constant.Constants

源文件：pro-base-common/src/main/java/com/ruoyi/common/constant/Constants.java
"""
from __future__ import annotations

from typing import Final


class Constants:
    """通用常量信息（Java 侧全部为 public static final）。

    【Java→Python】
    1) Java 的 public static final 是编译期常量，Python 没有等价物；这里用类属性 + 命名
       约定（全大写）表达，运行期仍可被重新赋值，属于语言能力差异，无法用代码消除。
    2) java.util.Locale.SIMPLIFIED_CHINESE → Python 用字符串 "zh_CN" 表示
       （Python 的 locale 模块不使用 Locale 对象）。
    3) Java 的 String[] 常量 → Python list（保持“元素可修改”的 Java 数组语义，
       若改成 tuple 会与 Java 行为不一致，例如 JOB_ERROR_STR[0] = "x" 在 Java 中合法）。
    4) Integer 类型的 CAPTCHA_EXPIRATION 仍是 int，Java 的装箱语义在 Python 中不存在。
    """

    # ---- 字符集
    UTF8 = "UTF-8"
    GBK = "GBK"

    # ---- 系统语言：Java 是 Locale.SIMPLIFIED_CHINESE
    DEFAULT_LOCALE = "zh_CN"

    # ---- 协议/前缀
    WWW = "www."
    HTTP = "http://"
    HTTPS = "https://"

    # ---- 通用标识
    SUCCESS = "0"
    FAIL = "1"
    LOGIN_SUCCESS = "Success"
    LOGOUT = "Logout"
    REGISTER = "Register"
    LOGIN_FAIL = "Error"

    # ---- 权限
    ALL_PERMISSION = "*:*:*"
    SUPER_ADMIN = "admin"
    ROLE_DELIMETER = ","
    PERMISSION_DELIMETER = ","

    # ---- 验证码/令牌
    CAPTCHA_EXPIRATION: Final[int] = 2
    TOKEN = "token"
    TOKEN_PREFIX = "Bearer "
    LOGIN_USER_KEY = "login_user_key"
    JWT_USERID = "userid"
    JWT_AVATAR = "avatar"
    JWT_CREATED = "created"
    JWT_AUTHORITIES = "authorities"

    # ---- 资源/远程调用
    RESOURCE_PREFIX = "/profile"
    LOOKUP_RMI = "rmi:"
    LOOKUP_LDAP = "ldap:"
    LOOKUP_LDAPS = "ldaps:"

    # ---- 白名单（Java String[]）
    JSON_WHITELIST_STR = ["org.springframework", "com.ruoyi"]
    JOB_WHITELIST_STR = ["com.ruoyi.quartz.task"]
    JOB_ERROR_STR = [
        "java.net.URL",
        "javax.naming.InitialContext",
        "org.yaml.snakeyaml",
        "org.springframework",
        "org.apache",
        "com.ruoyi.common.utils.file",
        "com.ruoyi.common.config",
        "com.ruoyi.generator",
    ]

    # ---- 流程结果
    FLOW_RESULT_ENTRUST_KEY = "entrust"
    FLOW_RESULT_CONTEXT_PREFIX = "委托"
    FLOW_RESULT_CONTEXT_SUFFIX = "办理"
    FLOW_ENTRUST_NAME = "委托"
    FLOW_IGNORE_TENANT_ID = "ignore"

    # ---- Redis 配置类 key
    SYS_CONFIG_KEY = "sys_config:"
    SYS_DICT_KEY = "sys_dict:"
    LOGIN_TOKEN_KEY = "login_tokens:"
    PROCUREMENT_MANAGER_ROLE_KEY = "cgjl_manager"
    CAPTCHA_CODE_KEY = "captcha_codes:"

    # ---- 字段/类型
    COLUMN_PRIMARY_KEY = "id"
    STRING_CLASS_KEY = "String"
    GENERATE_CODE_DICTIONARY_LIST_KEY_SUFFIX = "DictList"
    CHAR_COMMA = ","
    CHAR_BLANK = ""

    # ---- 角色
    dept_manager_role = "dept_manager"
    dept_duty_emp_role = "dept_duty_emp"

    # ---- 是否允许匿名访问
    D_ANNO = "anno-yes"

    # ---- 车辆/轨迹相关
    trail = "trail:"
    car_list = "car_list"
    car_list_jc = "car_list_jc"
    escapedType_20 = "20"
    station_ip = "station_ip"
    gantry_ip = "gantry_ip"
    car_uspicious = "car_uspicious"
    car_history_trail = "car_history_trail:"
    car_sync_time = "car_sync_time:"
    car_curent_trail = "car_curent_trail:"
    gantry_list = "gantry_list"
    gantry_list_data = "gantry_list_data:"
    dev_post = "dev_post"
    fwq_name = "fwq_name"
    station_info = "station_info"
    SECTION_ROAD_MAP = "section_road_map"

    # ---- 流水日期 key 前缀
    DATE_BORDER_WEIGHING_CAPTURE = "DATE_BorderWeighingCapture:"
    DATE_GANTRY_CAPTURE = "DATE_GantryCapture:"
    DATE_PROV_CAPTURE = "DATE_ProvCapture:"
    DATE_SERVICE_AREA_CAPTURE = "DATE_ServiceAreaCapture:"
    DATE_STATION_CAPTURE = "DATE_StationCapture:"
    DATE_FeeRecord = "DATE_FeeRecord:"
    DATE_FeeStationEnter = "DATE_FeeStationEnter:"
    DATE_FeeStationExit = "DATE_FeeStationExit:"

    # ---- 可疑车同步配置（注释中的默认值原样保留）
    redisBiteKey = "sys_config:syncSuspiciousCar_bite:"  # 比例默认为0.5
    redisTimeKey = "sys_config:syncSuspiciousCar_time:"  # 默认7天

    # ---- 快照/流水列表
    snapshotFlowList = "js_car_snapshot"
    feeRecordsList = "js_car_reerecords"
    trailFittingList = "js_car_trail_fitting"
    snapshotFlowTimeList = "snapshotFlowTimeList:"
    trailUnFittingList = "js_car_trail_unfitting"
    js_feeRecord = "js_feeRecord:"
