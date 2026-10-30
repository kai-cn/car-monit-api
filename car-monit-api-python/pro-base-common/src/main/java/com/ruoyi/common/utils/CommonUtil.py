# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.CommonUtil

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/CommonUtil.java
"""
from __future__ import annotations

import html
import os
import random
import re
from typing import Any, Optional

from com.ruoyi.common.utils.StringUtils import StringUtils

_RANDOM_BASE = "qwertyuioplkjhgfdsazxcvbnmQAZWSXEDCRFVTGBYHNUJMIKLOP0123456789"


def isNull(names: Any) -> str:
    """对象默认为空字符串：null → ""，否则 toString().trim()。"""
    if names is None:
        return ""
    return str(names).strip()


def isNotBlank(text: Optional[str]) -> bool:
    return StringUtils.isNotBlank(text)


def isBlank(text: Optional[str]) -> bool:
    return StringUtils.isBlank(text)


def isInteger(text: Optional[str]) -> bool:
    # Java: Pattern.compile("^[-\\+]?[\\d]*$").matcher(str).matches()
    # 注意空串也会匹配成功（\\d* 允许 0 次），属于原实现行为，原样保留。
    if text is None:
        return False
    return re.fullmatch(r"[-+]?[0-9]*", text) is not None


def isDouble(text: Optional[str]) -> bool:
    if text is None:
        return False
    return re.fullmatch(r"[-+]?[.0-9]*", text) is not None


def returnZero(text: Optional[str]) -> str:
    """为空就返回 "0"。"""
    if isNull(text) == "":
        return "0"
    return str(text).strip()


def isMobileDevice(request_header: Optional[str]) -> bool:
    """判断是否是手机端。

    【原样保留】Java 用的是 `indexOf(...) > 0`（不是 >= 0），
    因此请求头以 "android" 开头时反而返回 false —— 属于既有缺陷，不在此修复。
    """
    device_array = ("android", "mac os", "windows phone")
    if request_header is None:
        return False
    request_header = request_header.lower()
    for device in device_array:
        if request_header.find(device) > 0:
            return True
    return False


def isNum(text: Optional[str]) -> bool:
    if text is None:
        return False
    return re.fullmatch(r"(-?\d+)(\.\d+)?", text) is not None


def randomGen(place: int) -> str:
    """随机字符串（java.util.Random → random）。"""
    return "".join(random.choice(_RANDOM_BASE) for _ in range(place))


def deleteEnd(obj: Any) -> str:
    """删除结尾的一个 ","。"""
    text = isNull(obj)
    if text.endswith(","):
        text = text[: len(text) - 1]
    return text


def subStrLentg(obj: Any, length: int) -> str:
    """截取长度。

    【原样保留】Java 中截取的是 substring(0, len - 1)，即实际长度为 len-1，
    与“截取 len 个字符”的直觉不符，这里保持同样行为。
    """
    text = isNull(obj)
    if len(text) > length:
        text = text[: length - 1]
    return text


def getProjectUrl() -> str:
    """获取项目的根目录 - 绝对路径。

    【Java→Python】Java 取的是 ClassLoader.getResource("").getPath()（classpath 根，通常是
    target/classes/）。Python 没有 classpath 概念，这里返回当前工作目录，
    若需要“包根目录”请改用 ``os.path.dirname(__file__)``。
    """
    return os.getcwd() + os.sep


def getInnerText(html_text: Optional[str]) -> str:
    """获取 HTML 内的文本，不包含标签。"""
    if StringUtils.isNotBlank(html_text):
        # 去掉 html 的标签
        content = re.sub(r"</?[^>]+>", "", html_text)
        # 将多个空格合并成一个空格
        content = re.sub(r"(&nbsp;)+", "&nbsp;", content)
        # 反向转义字符（Spring HtmlUtils.htmlUnescape → html.unescape）
        content = html.unescape(content)
        return content.strip()
    return ""


def isNullInteger(names: Optional[int]) -> int:
    """对象默认为 0。

    【Java→Python】Java 的 Integer 可能为 null，直接 return names 会触发自动拆箱 NPE 风险；
    Python 的 None 判断后返回 int 即可。
    """
    if names is None:
        return 0
    return names


def repalacePicUrl(images_arry: Any) -> str:
    """图片域名替换。"""
    images_arry = isNull(images_arry)
    if isNotBlank(images_arry):
        if images_arry.find("http://jxjt.isilon.com/ifs") > -1:
            images_arry = images_arry.replace("http://jxjt.isilon.com/ifs", "http://36.200.30.144:9080")
        else:
            images_arry = images_arry.replace("http://jxjt.isilon.com", "http://36.200.30.144:9080")
    return images_arry


def repalaceSzdnTollName(toll_name: Any) -> str:
    """收费站名称替换：去掉“收费站/江西/站”。"""
    toll_name = isNull(toll_name)
    if isNotBlank(toll_name):
        toll_name = toll_name.replace("收费站", "")
        toll_name = toll_name.replace("江西", "")
        toll_name = toll_name.replace("站", "")
    return toll_name
