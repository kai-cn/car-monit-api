# AI Agent 设计文档（LangGraph 实现）

> 分支：`ai-agent-langgraph` · 基于 `car-monit-api-python` · 2026-11-21
> 状态：**设计稿（待独立会话审阅）**

## 1. 目标与范围

为 car-monit-api Python 版增加**生产级 AI Agent 功能**：用自然语言查询高速交通数据，
Agent 自动选择工具（查询/统计/导出/ES 状态），返回结构化答案。

### 1.1 为什么是 Agent 而不是简单 LLM 调用
- 业务查询有**确定性工具**（已有的 29 个 Controller / 110 端点对应 Service），LLM 只做意图识别和参数填充；
- 需要**多轮工具调用**（先查表 A 再查表 B）；
- 需要**可观测、可审计、可中断**（Java 开发者关注点）。

### 1.2 功能清单
| 功能 | 描述 | 工具 |
|---|---|---|
| 快照流水查询 | 按车牌/时间/路段查询 | `query_snapshot` |
| 统计聚合 | 按维度 Top-N | `group_stats` |
| 导出任务 | 提交/查询导出 | `submit_export` / `export_status` |
| ES 状态 | 索引健康度 | `es_status` |
| 全链路追踪 | 工具调用链记录 | trace_id |

## 2. 技术选型（以框架为基准，不为兼容性改官方写法）

| 层 | 选型 | 版本（2026-11 可用） | 理由 |
|---|---|---|---|
| Agent 框架 | **LangGraph** | `>=1.0,<2.0` | 显式 StateGraph 状态机；Java 开发者易理解（类似工作流引擎） |
| LLM 客户端 | `langchain-openai` | `>=1.0,<2.0` | OpenAI 兼容接口（可接豆包/通义/DeepSeek） |
| 工具定义 | `@tool` from `langchain.tools` | 随 langchain 1.x | 官方推荐；docstring 即 tool schema |
| 状态持久化 | `InMemorySaver` from `langgraph.checkpoint.memory` | 随 langgraph | 会话级多轮；生产可换 PostgresSaver |
| 结构化输出 | Pydantic v2 `response_format` | `>=2.7` | 与 FastAPI 同源 |
| Web 框架 | FastAPI | 现有 `>=0.115` | 新增 `/ai/agent/*` 路由，不碰原业务路由 |

**升级策略**：LangGraph/LangChain 相关包取 1.x 最新版；项目原有 fastapi/SQLAlchemy 等不动（避免回归）。

## 3. LangGraph 专属设计

### 3.1 为什么不用 `create_react_agent`
LangGraph v1 仍提供 `create_react_agent`（`langgraph.prebuilt`），官方推荐新项目用
LangChain v1 的 `create_agent`。本分支**刻意采用 StateGraph 原生显式编排**以展示可控工作流，
并非因为该 API 已弃用：

```
Start → agent(LLM decides) ──┬─ has tool_calls → tools(ToolNode) → agent
                             └─ no tool_calls   → END
```

这对应 Java 里的状态机：`StateGraph` = 流程定义，`node` = 处理步骤，`edge` = 转移条件。

### 3.2 状态定义（Java 对照：WorkflowContext）
```python
class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # 对话历史（追加语义）
    trace_id: str                                        # 链路追踪
    tool_calls_count: int                                # 防止无限循环
    error: str | None
```

### 3.3 节点
1. `call_model`：绑定工具的 LLM（`model.bind_tools(TOOLS)`），带 system prompt；
2. `tools`：官方 `ToolNode(TOOLS)`，执行工具并把 ToolMessage 追加到 state；
3. `should_continue`：条件边——有 `tool_calls` 且未超上限则回 `tools`，否则 `END`。

### 3.4 循环保护
`MAX_TOOL_ROUNDS = 8`；超过后在 state.error 写 "工具调用轮次超限"，强制 END。

## 4. 与现有项目的集成（不改框架写法）

### 4.1 新增目录
```
car-monit-api-python/
  app/ai_agent/
    __init__.py
    state.py          # AgentState（LangGraph 专属）
    tools.py          # @tool 定义的业务工具（两个分支共用语义）
    graph.py          # build_graph()：StateGraph 编排
    api.py            # APIRouter：POST /ai/agent/query
    models.py         # Pydantic 请求/响应
    settings.py       # AI 配置（从环境变量读取）
  tests/ai_agent/
    test_tools.py
    test_graph.py
    test_api_e2e.py
```

### 4.2 注册方式
`app/main.py` 中 `register_routes(app)` 之后追加 `app.include_router(ai_agent_router)`。
AI 路由**不进** `generated.py`（那是 Java 镜像路由表；AI 是 Python 独有功能）。

### 4.3 工具实现原则
- 工具函数调**已有 Service**（`TrafficSearchService` / `BigScreenStatsService` / `ExportTaskService` 等，
  见 `service/v3/v3_services.py`），不重复实现 SQL；
- 每个工具有 `try/except`，异常转结构化 `{"ok": false, "error": ...}`，不让 Agent 崩；
- 工具参数用 Pydantic 约束（时间格式、表名枚举），防止 LLM 传入非法值。

### 4.4 安全
- `/ai/agent/**` 走现有鉴权（Bearer token），不绕过；
- LLM 只通过工具访问数据，**禁止**直接执行 SQL/代码；
- 工具白名单固定，不接受运行时注册。

## 5. 配置（环境变量）
| 变量 | 默认 | 说明 |
|---|---|---|
| `AI_AGENT_MODEL` | `openai:gpt-4o-mini` | `provider:model` 格式 |
| `AI_AGENT_API_KEY` | (空) | LLM 密钥；空则用 FakeModel（测试） |
| `AI_AGENT_BASE_URL` | (空) | OpenAI 兼容端点 |
| `AI_AGENT_MAX_ROUNDS` | `8` | 工具轮次上限 |
| `AI_AGENT_TIMEOUT_SEC` | `30` | 单次 LLM 调用超时 |

## 6. 测试策略
- **单元测试**：工具函数直接调用（FakeModel 不需要真实 LLM）；
- **图测试**：`graph.invoke()` 用 FakeListChatModel 返回预定 tool_calls 序列；
- **E2E**：FastAPI TestClient 打 `/ai/agent/query`，断言结构化响应 + trace_id；
- **CI**：云 runner 跑 `pytest tests/ai_agent -q`（无需外部 API key）。

## 7. 风险与缓解
| 风险 | 缓解 |
|---|---|
| LLM 幻觉调错工具 | 工具名/参数用枚举约束；system prompt 明确工具边界 |
| 无限循环 | MAX_TOOL_ROUNDS + state.error |
| 敏感数据泄露 | 工具只返回聚合/脱敏字段；不暴露 filePath |
| 依赖升级冲突 | AI 依赖独立 extras `ai`，不装不影响原服务 |
