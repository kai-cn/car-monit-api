# -*- coding: utf-8 -*-
"""AI Agent（LangChain 分支）.

对外只暴露 ``router``（FastAPI）与 ``get_agent``（进程级单例 agent）。

【Java 开发者导读】
本包相当于 Java 的 ``com.ruoyi.ai`` 模块：
* ``settings`` = ``@ConfigurationProperties``（环境变量映射到配置对象）
* ``models``  = DTO（Pydantic v2，等价 Java record + Bean Validation）
* ``tools``   = ``@Tool`` 方法（LLM 可调用的确定性业务函数）
* ``agent``   = create_agent 工厂（LangChain v1 Agent = Model + Harness）
* ``api``     = ``@RestController``（FastAPI APIRouter）

框架官方写法优先：LangChain v1 的 create_agent 底层就是 LangGraph，
本分支不改写框架内部循环，而是用 middleware 注入横切逻辑（等价 Java Interceptor）。
"""
