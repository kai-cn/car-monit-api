# AI Agent 设计文档（LangChain 实现）

> 分支：`ai-agent-langchain` · 基于 `car-monit-api-python` · 2026-11-21
> 状态：**设计稿（待独立会话审阅）**

## 1. 目标与范围

与 LangGraph 分支**功能对等**：自然语言查询交通数据，Agent 自动调用工具，返回结构化答案。
本分支用 **LangChain v1 的 `create_agent`**——官方当前推荐的 agent harness（取代已弃用的 `create_react_agent`）。

### 1.1 LangChain v1 核心心智模型
```
Agent = Model + Harness
Harness = system_prompt + tools + middleware
```
Java 对照：`create_agent` 类似 Spring 的 `@Bean` 工厂方法，把 Model/Tools/Prompt 装配成一个可调用的 Runnable。

## 2. 技术选型（以框架为基准）

| 层 | 选型 | 版本 | 理由 |
|---|---|---|---|
| Agent 框架 | **LangChain** | `>=1.5,<2.0` | 官方 `create_agent`，内置工具循环 |
| LLM 客户端 | `langchain-openai` | `>=1.8,<2.0` | OpenAI 兼容 |
| 工具 | `@tool` from `langchain.tools` | 随 langchain 1.x | 官方推荐 |
| 结构化输出 | `response_format=AgentAnswer` | Pydantic v2 | 官方 API |
| Middleware | `AgentMiddleware` | 随 langchain 1.x | 日志/超时/错误包装 |
| 会话记忆 | `InMemorySaver` (LangGraph checkpoint) | 随 langgraph | `create_agent` 底层是 LangGraph |

**关键差异**：LangChain `create_agent` 内部**已经构建了图**；本分支不显式写 `StateGraph`，
而是通过 middleware 注入横切逻辑（这是框架官方写法，不为兼容而改写）。

## 3. LangChain 专属设计

### 3.1 Agent 构建
```python
from langchain.agents import create_agent
from langchain.tools import tool

agent = create_agent(
    model=model,                    # BaseChatModel 实例或 "provider:model" 字符串
    tools=TOOLS,
    system_prompt=SYSTEM_PROMPT,
    response_format=AgentAnswer,    # 结构化输出
    middleware=[TraceMiddleware()], # 追踪工具调用
    checkpointer=InMemorySaver(),   # 多轮会话
)
```
调用：`agent.invoke({"messages":[{"role":"user","content":question}]},
config={"configurable":{"thread_id": session_id}})` →
从 `result["structured_response"]` 取 `AgentAnswer`。

### 3.2 Middleware（Java 对照：HandlerInterceptor）
```
TraceMiddleware extends AgentMiddleware
  before_agent: 生成 trace_id，写入 state
  wrap_tool_call: 记录工具名/参数/耗时/成功标志（不记完整 data）
  after_agent: 汇总 tool_calls 到 structured_response
```
为什么用 middleware：LangChain v1 把横切关注点统一到 middleware，
不在工具函数里散落日志代码（与 Java AOP 思路一致）。

### 3.3 结构化输出
`AgentAnswer` Pydantic 模型：
```python
class AgentAnswer(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)
    sources: list[str] = []   # 工具名列表，便于审计
```
`response_format` 让模型最后一步输出严格 JSON，避免解析自由文本。

## 4. 与现有项目的集成

目录结构与 LangGraph 分支一致（`app/ai_agent/`），但内部实现文件不同：
```
app/ai_agent/
  settings.py, models.py, tools.py     # 与 LangGraph 分支语义一致
  agent.py        # create_agent 工厂（本分支专属，替代 graph.py/state.py）
  middleware.py   # TraceMiddleware（本分支专属）
  api.py          # POST /ai/agent/query（对外契约一致）
  fake_model.py   # 测试模型
```
对外 HTTP 契约与 LangGraph 分支**完全一致**（见 SPEC §2），便于 A/B 对比。

### 4.1 工具实现原则（同 LangGraph 分支）
- 调已有 Service，不重写 SQL；
- 异常结构化返回；
- 参数 Pydantic 约束；
- 工具白名单固定。

### 4.2 安全（同 LangGraph 分支）
- `/ai/agent/**` 复用现有鉴权；
- LLM 不直接执行 SQL；
- 工具只返回脱敏/聚合数据。

## 5. 配置（同 LangGraph 分支）
`AI_AGENT_MODEL` / `AI_AGENT_API_KEY` / `AI_AGENT_BASE_URL` / `AI_AGENT_MAX_ROUNDS` / `AI_AGENT_TIMEOUT_SEC`。

## 6. 测试策略（同 LangGraph 分支）
FakeModel → 单测工具 / agent 调用链 / HTTP E2E；云 runner 无需真实 LLM key。

## 7. 风险与缓解
| 风险 | 缓解 |
|---|---|
| middleware API 随版本变化 | 锁定 `langchain>=1.5,<2.0`，CI 固定版本 |
| 结构化输出失败 | response_format + Pydantic 校验；失败降级为文本 answer |
| 会话状态丢失 | InMemorySaver（生产可换 PostgresSaver） |
| 与现有包冲突 | AI 依赖放 extras `ai`，独立 `requirements-ai.txt` |
