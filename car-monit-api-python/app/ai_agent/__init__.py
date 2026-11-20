# -*- coding: utf-8 -*-
"""AI Agent（LangGraph 分支）.

对外只暴露 ``router``（FastAPI）与 ``get_graph``（进程级单例图）。

【Java 开发者导读】
本包相当于 Java 的 ``com.ruoyi.ai`` 模块：
* ``settings`` = ``@ConfigurationProperties``（环境变量映射到配置对象）
* ``models``  = DTO（Pydantic v2，等价 Java record + Bean Validation）
* ``tools``   = ``@Tool`` 方法（LLM 可调用的确定性业务函数）
* ``graph``   = 工作流引擎定义（StateGraph：状态 + 节点 + 边）
* ``api``     = ``@RestController``（FastAPI APIRouter）

框架官方写法优先：不为了兼容旧代码改写 LangGraph 的 StateGraph/ToolNode/checkpointer API。
"""
