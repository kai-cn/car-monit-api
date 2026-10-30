# -*- coding: utf-8 -*-
"""com.ruoyi.common.constant.CacheConstants

源文件：pro-base-common/src/main/java/com/ruoyi/common/constant/CacheConstants.java
"""


class CacheConstants:
    """缓存的 key 常量。

    【Java→Python】Java 的 public static final String 常量在 Python 中是普通类属性；
    访问方式保持一致：CacheConstants.LOGIN_TOKEN_KEY。
    """

    LOGIN_TOKEN_KEY = "login_tokens:"          # 登录用户 redis key
    CAPTCHA_CODE_KEY = "captcha_codes:"        # 验证码 redis key
    SYS_CONFIG_KEY = "sys_config:"             # 参数管理 cache key
    SYS_DICT_KEY = "sys_dict:"                 # 字典管理 cache key
    REPEAT_SUBMIT_KEY = "repeat_submit:"       # 防重提交 redis key
    RATE_LIMIT_KEY = "rate_limit:"             # 限流 redis key
    PWD_ERR_CNT_KEY = "pwd_err_cnt:"           # 登录账户密码错误次数 redis key
