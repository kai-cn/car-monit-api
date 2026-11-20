# AI Agent 实现规格（LangChain 分支）

> 状态：**规格稿（待独立会话审阅）** · 对应设计 `AI-AGENT-DESIGN.md`
> 本文件是实现的唯一契约；实现不得偏离以下签名/路径/行为。
> 对外 HTTP 契约与 `ai-agent-langgraph` 分支一致。

## 1. 文件清单与职责

| 路径 | 必须导出的符号 | 职责 |
|---|---|---|
| `app/ai_agent/__init__.py` | — | 包标记 |
| `app/ai_agent/settings.py` | `AgentSettings`, `get_agent_settings()` | 环境变量解析 |
| `app/ai_agent/models.py` | `AgentQueryRequest`, `AgentQueryResponse`, `ToolCallRecord`, `AgentAnswer` | Pydantic v2 DTO |
| `app/ai_agent/tools.py` | `TOOLS`, `query_snapshot`, `group_stats`, `submit_export`, `export_status`, `es_status` | `@tool` 业务工具（与 LangGraph 分支语义一致） |
| `app/ai_agent/middleware.py` | `TraceMiddleware` | 追踪工具调用（LangChain 专属） |
| `app/ai_agent/agent.py` | `build_agent(checkpointer=None)`, `get_agent()` | `create_agent` 工厂 |
| `app/ai_agent/api.py` | `router`, `query_agent` | FastAPI `APIRouter(prefix="/ai/agent")` |
| `app/ai_agent/fake_model.py` | `FakeAgentModel` | 测试模型 |
| `tests/ai_agent/test_tools.py` | 4+ 用例 | 工具契约 |
| `tests/ai_agent/test_agent.py` | 3+ 用例 | agent 调用链与 middleware |
| `tests/ai_agent/test_api_e2e.py` | 3+ 用例 | HTTP 端到端 |

## 2. 精确接口契约

### 2.1 `AgentSettings` / DTO
与 LangGraph 分支 SPEC §2.1/§2.2 **完全一致**（含 `AgentQueryRequest`/`AgentQueryResponse`/`ToolCallRecord`）。
额外导出：
```python
class AgentAnswer(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1, default=0.8)
    sources: list[str] = []
```

### 2.2 工具签名
与 LangGraph 分支 SPEC §2.3 **完全一致**（6 个工具，统一返回 `{"ok":...}` JSON 字符串）。

### 2.3 Agent 工厂
```python
def build_agent(checkpointer: Any = None) -> Any:
    return create_agent(
        model=_build_model(),
        tools=TOOLS,
        system_prompt=SYSTEM_PROMPT,
        response_format=AgentAnswer,
        middleware=[TraceMiddleware()],
        checkpointer=checkpointer or InMemorySaver(),
    )
```
`_build_model()`：若 `settings.api_key` 空 → `FakeAgentModel()`；否则 `ChatOpenAI(model=..., api_key=..., base_url=...)`。

### 2.4 TraceMiddleware
继承 `AgentMiddleware`，实现：
- `before_agent(state, runtime)`：生成 `trace_id`，记录开始时间；
- `wrap_tool_call(request, handler)`：调用 `handler(request)`，捕获异常，记录
  `{name, args, ok, elapsed_ms, result_preview}` 到实例级 buffer（每次 invoke 前清空）；
- `after_agent(state, runtime)`：把 buffer 汇总到 state（供 API 层读取）。

> **注意**：中间件 API 以安装的 langchain 1.x 实际签名为准；若与规格有出入，
> 以实现时 `inspect.signature` 校验结果为准，并在代码注释中说明与 Java Interceptor 的类比。

### 2.5 API
```
POST /ai/agent/query
  与 LangGraph 分支完全一致的 req/resp/错误语义。
  实现：get_agent().invoke({"messages":[{"role":"user","content":question}]},
        config={"configurable":{"thread_id": session_id or trace_id}})
  从 result["structured_response"] 取 AgentAnswer；从 middleware buffer 取 tool_calls。
```

## 3. 依赖变更
同 LangGraph 分支：extras `ai` + `requirements-ai.txt`：
```
langchain>=1.5,<2.0
langchain-openai>=1.8,<2.0
langgraph>=1.0,<2.0   # create_agent 底层依赖
pydantic>=2.7,<3.0
```

## 4. CI/CD 规格
同 LangGraph 分支：`.github/workflows/ai-agent-e2e.yml`，云 runner 跑 pytest + smoke，
不回显密钥。

## 5. 验收标准（DoD）
- [ ] `pytest tests/ai_agent -q` 全绿，覆盖率 ≥70%
- [ ] HTTP 契约与 LangGraph 分支一致（字段/状态码）
- [ ] 云 runner e2e workflow success
- [ ] 设计/spec 经独立会话审阅通过
- [ ] 两分支异同说明文档完成
