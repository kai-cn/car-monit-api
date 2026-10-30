# -*- coding: utf-8 -*-
"""com.ruoyi.common.utils.ServletUtils

源文件：pro-base-common/src/main/java/com/ruoyi/common/utils/ServletUtils.java

【Java→Python】整体说明
1) ``RequestContextHolder.getRequestAttributes()`` 是 Spring 基于 **ThreadLocal** 保存
   当前请求的机制；Python 没有 Servlet 容器，这里用 ``threading.local`` 复刻：
   Web 框架（Flask/FastAPI）在请求进入时调用 ``RequestContextHolder.setRequestAttributes``，
   业务代码的 ``ServletUtils.getRequest()`` 就能拿到同一个请求对象。
2) ``HttpServletRequest / HttpServletResponse / HttpSession`` 是接口，
   Python 侧用鸭子类型的 ``_HttpServletRequest`` / ``_HttpServletResponse`` 替身，
   只实现本类用到的方法（getParameter/getHeader/getRequestURI/getSession/
   setStatus/setContentType/setCharacterEncoding/getWriter）。
3) ``getParameter`` / ``getParameterToInt`` / ``getParameterToBool`` 各有两个重载
   （带不带默认值），Python 合并为“default 关键字为 None 即不带默认值”。
4) ``URLEncoder.encode`` / ``URLDecoder.decode``：
   - Java 的 ``URLEncoder`` 把空格编码成 ``+``、保留 ``*``、编码 ``~``；
     Python 的 ``quote_plus(safe="*")`` 保留 ``*`` 但不编码 ``~``，
     因此额外做一次 ``~`` → ``%7E`` 替换以对齐 Java 输出。
   - Java 遇到非法 ``%`` 序列抛 IllegalArgumentException；Python 的 ``unquote_plus``
     会原样保留，这里不额外抛错（差异已在注释标明）。
5) ``IOException`` → ``OSError``；``printStackTrace`` → ``traceback.print_exc()``。
6) ``Collections.unmodifiableMap`` → ``types.MappingProxyType``（只读视图）。
"""
from __future__ import annotations

import threading
import traceback
import urllib.parse
from types import MappingProxyType
from typing import Any, Optional

from com.ruoyi.common.constant.Constants import Constants
from com.ruoyi.common.core.text.Convert import Convert
from com.ruoyi.common.utils.StringUtils import StringUtils


class _HttpSession:
    """``HttpSession`` 替身：基于 dict 的属性表。"""

    def __init__(self) -> None:
        self._attributes: dict[str, Any] = {}

    def getAttribute(self, name: str) -> Any:
        return self._attributes.get(name)

    def setAttribute(self, name: str, value: Any) -> None:
        self._attributes[name] = value

    def removeAttribute(self, name: str) -> None:
        self._attributes.pop(name, None)

    def getId(self) -> str:
        return str(id(self))


class _PrintWriter:
    """``java.io.PrintWriter`` 替身：print 不换行，println 换行。"""

    def __init__(self) -> None:
        self._buffer: list[str] = []

    def print(self, text: Any) -> None:
        self._buffer.append("" if text is None else str(text))

    def println(self, text: Any = None) -> None:
        self._buffer.append("" if text is None else str(text))
        self._buffer.append("\n")

    def getValue(self) -> str:
        return "".join(self._buffer)


class _HttpServletRequest:
    """``HttpServletRequest`` 替身（按需扩展）。"""

    def __init__(self, parameters: Optional[dict[str, list[str]]] = None,
                 headers: Optional[dict[str, str]] = None,
                 request_uri: str = "/") -> None:
        self._parameters = parameters or {}
        self._headers = headers or {}
        self._request_uri = request_uri
        self._session = _HttpSession()

    def getParameter(self, name: str) -> Optional[str]:
        """Servlet 语义：取第一个值，不存在返回 null。"""
        values = self._parameters.get(name)
        return values[0] if values else None

    def getParameterMap(self) -> dict[str, list[str]]:
        return self._parameters

    def getHeader(self, name: str) -> Optional[str]:
        return self._headers.get(name)

    def getRequestURI(self) -> str:
        return self._request_uri

    def getSession(self) -> _HttpSession:
        return self._session


class _HttpServletResponse:
    """``HttpServletResponse`` 替身（按需扩展）。"""

    def __init__(self) -> None:
        self._status = 200
        self._content_type: Optional[str] = None
        self._character_encoding: Optional[str] = None
        self._writer = _PrintWriter()

    def setStatus(self, status: int) -> None:
        self._status = status

    def getStatus(self) -> int:
        return self._status

    def setContentType(self, content_type: str) -> None:
        self._content_type = content_type

    def getContentType(self) -> Optional[str]:
        return self._content_type

    def setCharacterEncoding(self, character_encoding: str) -> None:
        self._character_encoding = character_encoding

    def getCharacterEncoding(self) -> Optional[str]:
        return self._character_encoding

    def getWriter(self) -> _PrintWriter:
        return self._writer


class _ServletRequestAttributes:
    """``ServletRequestAttributes`` 替身：持有 request / response。"""

    def __init__(self, request: _HttpServletRequest,
                 response: Optional[_HttpServletResponse] = None) -> None:
        self._request = request
        self._response = response if response is not None else _HttpServletResponse()

    def getRequest(self) -> _HttpServletRequest:
        return self._request

    def getResponse(self) -> _HttpServletResponse:
        return self._response


class RequestContextHolder:
    """``RequestContextHolder`` 替身：threading.local 保存当前请求属性。

    【Java→Python】Spring 的 RequestContextHolder 用 InheritableThreadLocal；
    Python 的 threading.local 不具备父子线程继承能力，
    若需要跨线程传递，必须在子线程里显式 setRequestAttributes（注释标明该差异）。
    """

    _local = threading.local()

    @staticmethod
    def getRequestAttributes() -> Optional[_ServletRequestAttributes]:
        return getattr(RequestContextHolder._local, "attributes", None)

    @staticmethod
    def setRequestAttributes(attributes: Optional[_ServletRequestAttributes]) -> None:
        RequestContextHolder._local.attributes = attributes

    @staticmethod
    def resetRequestAttributes() -> None:
        RequestContextHolder._local.attributes = None


class ServletUtils:
    """客户端工具类。"""

    # ------------------------------------------------------------------ 参数
    @staticmethod
    def getParameter(name: str, default_value: Optional[str] = None) -> Optional[str]:
        """获取 String 参数（两个重载合并）。"""
        if default_value is None:
            return ServletUtils.getRequest().getParameter(name)
        return Convert.toStr(ServletUtils.getRequest().getParameter(name), default_value)

    @staticmethod
    def getParameterToInt(name: str, default_value: Optional[int] = None) -> Optional[int]:
        """获取 Integer 参数（两个重载合并）。"""
        if default_value is None:
            return Convert.toInt(ServletUtils.getRequest().getParameter(name))
        return Convert.toInt(ServletUtils.getRequest().getParameter(name), default_value)

    @staticmethod
    def getParameterToBool(name: str, default_value: Optional[bool] = None) -> Optional[bool]:
        """获取 Boolean 参数（两个重载合并）。"""
        if default_value is None:
            return Convert.toBool(ServletUtils.getRequest().getParameter(name))
        return Convert.toBool(ServletUtils.getRequest().getParameter(name), default_value)

    @staticmethod
    def getParams(request: Any) -> Any:
        """获得所有请求参数（返回只读 Map）。"""
        param_map = request.getParameterMap()
        # Java: Collections.unmodifiableMap(map)
        return MappingProxyType(param_map)

    @staticmethod
    def getParamMap(request: Any) -> dict[str, str]:
        """获得所有请求参数（值数组用逗号拼接）。"""
        params: dict[str, str] = {}
        for key, values in ServletUtils.getParams(request).items():
            params[key] = StringUtils.join(values, ",")
        return params

    # ------------------------------------------------------------------ 上下文对象
    @staticmethod
    def getRequest() -> _HttpServletRequest:
        return ServletUtils.getRequestAttributes().getRequest()

    @staticmethod
    def getResponse() -> _HttpServletResponse:
        return ServletUtils.getRequestAttributes().getResponse()

    @staticmethod
    def getSession() -> _HttpSession:
        return ServletUtils.getRequest().getSession()

    @staticmethod
    def getRequestAttributes() -> _ServletRequestAttributes:
        # 【Java→Python】Java 是强制类型转换 (ServletRequestAttributes)；
        # Python 没有跨线程的 RequestContextHolder，未初始化时自然返回 None，
        # 后续调用 getRequest() 会抛 AttributeError（等价于 Java 的 NPE）。
        return RequestContextHolder.getRequestAttributes()

    # ------------------------------------------------------------------ 渲染
    @staticmethod
    def renderString(response: _HttpServletResponse, string: Optional[str]) -> None:
        """将字符串渲染到客户端。"""
        try:
            response.setStatus(200)
            response.setContentType("application/json")
            response.setCharacterEncoding("utf-8")
            response.getWriter().print(string)
        except OSError:
            # Java: catch (IOException e) { e.printStackTrace(); }
            traceback.print_exc()

    @staticmethod
    def isAjaxRequest(request: _HttpServletRequest) -> bool:
        """是否是 Ajax 异步请求。"""
        accept = request.getHeader("accept")
        if accept is not None and "application/json" in accept:
            return True

        x_requested_with = request.getHeader("X-Requested-With")
        if x_requested_with is not None and "XMLHttpRequest" in x_requested_with:
            return True

        uri = request.getRequestURI()
        if StringUtils.inStringIgnoreCase(uri, ".json", ".xml"):
            return True

        ajax = request.getParameter("__ajax")
        return StringUtils.inStringIgnoreCase(ajax, "json", "xml")

    # ------------------------------------------------------------------ 编解码
    @staticmethod
    def urlEncode(string: Optional[str]) -> Optional[str]:
        """内容编码。"""
        try:
            # URLEncoder.encode(str, Constants.UTF8)
            # 【Java→Python】safe="*" 对齐 Java 不编码 '*'；Java 会把 '~' 编成 %7E，
            # 而 Python 的 quote_plus 始终保留 '~'，故再替换一次。
            return urllib.parse.quote_plus(string, safe="*", encoding=Constants.UTF8) \
                .replace("~", "%7E")
        except (LookupError, TypeError):
            # Java: catch (UnsupportedEncodingException e) { return StringUtils.EMPTY; }
            return StringUtils.EMPTY

    @staticmethod
    def urlDecode(string: Optional[str]) -> Optional[str]:
        """内容解码。"""
        try:
            return urllib.parse.unquote_plus(string, encoding=Constants.UTF8)
        except (LookupError, TypeError):
            return StringUtils.EMPTY
