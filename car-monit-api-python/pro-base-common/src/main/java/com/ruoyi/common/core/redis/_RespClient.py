# -*- coding: utf-8 -*-
"""Minimal RESP2 client used by the ``RedisCache`` stand-in.

【无 Java 源文件：框架基础设施替身】
Java 侧由 Lettuce（``spring-boot-starter-data-redis`` 的默认客户端）完成
``RedisTemplate`` 与 Redis 之间的字节流收发。Python 端没有等价依赖，这里用
一百行 RESP2 协议实现只读所需的 ``GET``，避免为了「读一个配置项」而引入第三方
redis 客户端。

【为什么只读、只放行标量】
Java（:9902）和 Python（:9901）连的是同一个 Redis 库。实测该库里的对象值是这样的：

    {"@type":"com.ruoyi.base.domain.OdsSzdnProvinceBorderVehicleWeightNewstructure",
     "axleArray":"[{\\"axleNo\\":1,...}]", "vehicleWeight":52650L, ...}

FastJson 把 Java 类型一起写了进去，``52650L`` 甚至不是合法 JSON，Java 靠
``@type`` 还原成实体。Python 侧无法还原同一个 Java 对象：直接返回 dict 会改变
响应结构（缺 null 键、日期格式不同），比缓存未命中更糟 —— 未命中时业务代码会
走数据库，得到的实体与 Java 序列化出来的完全一致。

因此只对**标量**值（str / int / float / bool）做读穿透；
``sys_config:data_query`` 这类配置正是标量，与 Java 行为完全一致。
写操作仍然只在进程内，原因同上：回写会破坏 Java 侧的解析。
"""
from __future__ import annotations

import json
import logging
import os
import socket
import threading
from typing import Any, Optional
from urllib.parse import unquote, urlsplit

log = logging.getLogger(__name__)

__all__ = ["RespClient", "RedisReplyError", "open_from_env"]


class RedisReplyError(RuntimeError):
    """Redis 返回 ``-ERR ...`` 时抛出（对应 JedisException / RedisSystemException）。"""


class RespClient:
    """RESP2（Redis 序列化协议）的最小客户端。

    只实现只读穿透用到的 ``PING`` / ``AUTH`` / ``SELECT`` / ``GET``。所有命令
    串行执行（加锁）；连接断开后下一次调用自动重连 —— 与 Lettuce 在单进程
    FastAPI 场景下的连接复用行为等价。
    """

    def __init__(self, host: str, port: int = 6379, database: int = 0,
                 password: Optional[str] = None, timeout: float = 2.0) -> None:
        self.host = host
        self.port = port
        self.database = database
        self.password = password
        self.timeout = timeout
        self.__socket: Optional[socket.socket] = None
        self.__reader: Any = None
        self.__lock = threading.Lock()

    # ------------------------------------------------------------------ 连接
    def _connect(self) -> None:
        sock = socket.create_connection((self.host, self.port), self.timeout)
        sock.settimeout(self.timeout)
        self.__socket = sock
        self.__reader = sock.makefile("rb")
        if self.password:
            self._execute("AUTH", self.password)
        # spring.redis.database 默认 0；非 0 时需要 SELECT
        if self.database:
            self._execute("SELECT", str(self.database))

    def close(self) -> None:
        for closer in (self.__reader, self.__socket):
            try:
                if closer is not None:
                    closer.close()
            except OSError:  # pragma: no cover - 关闭失败的 socket 无需处理
                pass
        self.__reader = None
        self.__socket = None

    def _execute(self, *args: Any) -> Any:
        chunks = [b"*%d\r\n" % len(args)]
        for arg in args:
            data = arg if isinstance(arg, bytes) else str(arg).encode("utf-8")
            chunks.append(b"$%d\r\n%s\r\n" % (len(data), data))
        assert self.__socket is not None
        self.__socket.sendall(b"".join(chunks))
        return self._read_reply()

    def _call(self, *args: Any) -> Any:
        with self.__lock:
            try:
                if self.__socket is None:
                    self._connect()
                return self._execute(*args)
            except OSError:
                # 连接已坏：丢弃，让下一次调用重连（Lettuce 同样会重连）
                self.close()
                raise

    def _read_reply(self) -> Any:
        line = self.__reader.readline()
        if not line:
            raise OSError("redis connection closed")
        prefix, body = line[:1], line[1:-2]
        if prefix == b"+":
            return body.decode("utf-8", "replace")
        if prefix == b"-":
            raise RedisReplyError(body.decode("utf-8", "replace"))
        if prefix == b":":
            return int(body)
        if prefix == b"$":
            length = int(body)
            if length < 0:
                return None
            return self.__reader.read(length + 2)[:-2]
        if prefix == b"*":
            count = int(body)
            if count < 0:
                return None
            return [self._read_reply() for _ in range(count)]
        raise RedisReplyError("unexpected reply prefix %r" % prefix)

    # ------------------------------------------------------------------ 只读指令
    def getRaw(self, key: str) -> Optional[bytes]:
        return self._call("GET", key)

    def getScalar(self, key: str) -> Any:
        """GET 并反序列化，但只放行标量（见模块说明）。

        返回 ``None`` 既表示「键不存在」，也表示「值是 Java 对象，Python 还原
        不了」—— 两种情况对调用方的含义相同：当作缓存未命中，回源数据库。
        """
        raw = self.getRaw(key)
        if raw is None:
            return None
        try:
            value = json.loads(raw.decode("utf-8", "replace"))
        except ValueError:
            # FastJson 的 123L / new Date(...) 等非标准写法，Python 无法还原
            return None
        return value if isinstance(value, (str, int, float, bool)) else None


def open_from_env() -> Optional[RespClient]:
    """按 ``CAR_MONIT_REDIS_URL`` 打开只读客户端；未配置或连不上时返回 ``None``。

    URL 形如 ``redis://[:password@]host:port/db``。未配置时保持纯内存行为，
    单元测试因此完全不依赖外部 Redis。
    """
    url = os.environ.get("CAR_MONIT_REDIS_URL", "").strip()
    if not url:
        return None
    parts = urlsplit(url)
    if parts.scheme not in ("redis", "rediss") or not parts.hostname:
        log.warning("CAR_MONIT_REDIS_URL 无法解析，继续使用进程内缓存: %s", url)
        return None
    database = int((parts.path or "/0").lstrip("/") or 0)
    client = RespClient(
        host=parts.hostname,
        port=parts.port or 6379,
        database=database,
        password=unquote(parts.password) if parts.password else None,
    )
    try:
        client._call("PING")
    except Exception as error:  # noqa: BLE001 - 缓存不可用不应阻断启动
        log.warning("真实 Redis 不可用（%s），继续使用进程内缓存: %s", url, error)
        client.close()
        return None
    log.info("RedisCache 只读穿透已接入真实 Redis: %s", url)
    return client
