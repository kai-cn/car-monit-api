# -*- coding: utf-8 -*-
"""com.ruoyi.base.forest.HttpSysUtilApiService

源文件：pro-business-api/src/main/java/com/ruoyi/base/forest/HttpSysUtilApiService.java

Java 侧是 **Forest 声明式 HTTP 客户端接口**：
    @BaseRequest(baseURL = "#{sysbaseUrl}/manager/suspicious")
    public interface HttpSysUtilApiService {
        @Post("/syncSuspiciousCarTask")
        JSONObject syncSuspiciousCarTask(@JSONBody SuspiciousCarVO suspiciousCarVO);
    }

【Java→Python 关键差异】
1) Forest 通过 `@BaseRequest` / `@Post` / `@JSONBody` 注解在**运行时生成动态代理**：
   调用方法即发起 HTTP 请求，参数按 `@JSONBody` 序列化为 JSON 请求体，
   响应体反序列化成 `JSONObject`。Python 标准库没有这种"AOP 代理"机制。
2) 本文件保留**接口契约**（ABC + 方法签名），并提供默认实现
   `ForestHttpSysUtilApiService`：**不发真实 HTTP**，直接返回 `code=200` 的响应，
   便于重构验证与单元测试。真实调用由使用方注入自定义实现（例如基于 urllib/requests）。
3) `#{sysbaseUrl}` 是 Forest 的配置占位符（来自 application.yml 的 `sysbaseUrl`），
   Python 侧保留为类属性 `BASE_URL_PLACEHOLDER`，实现类可用构造器覆盖。
4) `@JSONBody` 的序列化规则：字段名取自 Java Bean 属性名（camelCase），null 字段按
   Forest 默认配置**不忽略**（序列化为 null）。默认实现用 `JSON.toJSONString` 对齐该行为。
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from com.alibaba.fastjson2.JSON import JSON
from com.alibaba.fastjson2.JSONObject import JSONObject
from com.ruoyi.base.domain.SuspiciousCarVO import SuspiciousCarVO
from com.ruoyi.common.constant.HttpStatus import HttpStatus

log = logging.getLogger(__name__)

__all__ = ["HttpSysUtilApiService", "ForestHttpSysUtilApiService"]


class HttpSysUtilApiService(ABC):
    """`HttpSysUtilApiService` 接口（Forest 客户端契约）。

    【Java→Python】Java 接口方法天然是抽象的；Python 用 `abc.abstractmethod` 表达。
    """

    # Forest: @BaseRequest(baseURL = "#{sysbaseUrl}/manager/suspicious")
    BASE_URL_PLACEHOLDER = "#{sysbaseUrl}/manager/suspicious"
    SYNC_SUSPICIOUS_CAR_TASK_PATH = "/syncSuspiciousCarTask"

    @abstractmethod
    def syncSuspiciousCarTask(self, suspiciousCarVO: SuspiciousCarVO) -> JSONObject:
        """POST {sysbaseUrl}/manager/suspicious/syncSuspiciousCarTask（@JSONBody 请求体）。"""
        raise NotImplementedError


class ForestHttpSysUtilApiService(HttpSysUtilApiService):
    """默认实现：不发起真实 HTTP，返回 code=200 的 JSONObject。

    【Java→Python】Spring 容器注入的是 Forest 生成的代理对象；Python 没有容器，
    由使用方选择注入本默认实现（离线/测试）或自定义实现（真实网络调用）。
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        # Java: @BaseRequest 的 baseURL 由森林配置解析，这里允许显式覆盖
        self.base_url: str = base_url or self.BASE_URL_PLACEHOLDER

    def syncSuspiciousCarTask(self, suspiciousCarVO: SuspiciousCarVO) -> JSONObject:
        # 【Java→Python】真实请求体序列化（对应 @JSONBody）：
        # Java 序列化的是 SuspiciousCarVO 的属性；这里保留同样的调用与日志，
        # 但不真正建立网络连接（离线替身）。
        body = JSON.toJSONString(suspiciousCarVO)
        log.info("POST %s%s 请求体长度: %s", self.base_url,
                 self.SYNC_SUSPICIOUS_CAR_TASK_PATH, len(body))

        # Forest 会把响应体反序列化成 JSONObject；替身直接构造成功响应
        response = JSONObject()
        response.put("code", HttpStatus.SUCCESS)
        response.put("msg", "操作成功")
        return response
