# AI Agent 实现规格（LangGraph 分支）

> 状态：**规格稿（待独立会话审阅）** · 对应设计 `AI-AGENT-DESIGN.md`
> 本文件是实现的唯一契约；实现不得偏离以下签名/路径/行为。

## 1. 文件清单与职责

| 路径 | 必须导出的符号 | 职责 |
|---|---|---|
| `app/ai_agent/__init__.py` | — | 包标记 |
| `app/ai_agent/settings.py` | `AgentSettings`, `get_agent_settings()` | 环境变量解析，等价 Java `@ConfigurationProperties` |
| `app/ai_agent/models.py` | `AgentQueryRequest`, `AgentQueryResponse`, `ToolCallRecord` | Pydantic v2 DTO |
| `app/ai_agent/tools.py` | `TOOLS`, `query_snapshot`, `group_stats`, `submit_export`, `export_status`, `es_status` | `@tool` 装饰的业务工具 |
| `app/ai_agent/state.py` | `AgentState`, `MAX_TOOL_ROUNDS` | LangGraph 状态 TypedDict |
| `app/ai_agent/graph.py` | `build_graph(checkpointer=None)`, `compile_agent()` | StateGraph 编排 |
| `app/ai_agent/api.py` | `router`, `query_agent` | FastAPI `APIRouter(prefix="/ai/agent")` |
| `app/ai_agent/fake_model.py` | `FakeAgentModel` | 测试用模型，返回预定 tool_calls |
| `tests/ai_agent/test_tools.py` | 4+ 用例 | 工具契约 |
| `tests/ai_agent/test_graph.py` | 3+ 用例 | 图流转与循环保护 |
| `tests/ai_agent/test_api_e2e.py` | 3+ 用例 | HTTP 端到端 |

## 2. 精确接口契约

### 2.1 `AgentSettings`
```python
@dataclass(frozen=True)
class AgentSettings:
    model: str            # AI_AGENT_MODEL, default "openai:gpt-4o-mini"
    api_key: str          # AI_AGENT_API_KEY, default ""
    base_url: str         # AI_AGENT_BASE_URL, default ""
    max_rounds: int       # AI_AGENT_MAX_ROUNDS, default 8
    timeout_sec: float    # AI_AGENT_TIMEOUT_SEC, default 30.0

def get_agent_settings() -> AgentSettings: ...  # 每次读 env（便于测试 monkeypatch）
```

### 2.2 DTO
```python
class AgentQueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    session_id: str | None = None
    tables: list[Literal["snapshot", "fee", "trail"]] = ["snapshot", "fee", "trail"]

class ToolCallRecord(BaseModel):
    name: str
    args: dict[str, Any]
    ok: bool
    result_preview: str = Field(max_length=300)  # 不返回完整数据，防泄露

class AgentQueryResponse(BaseModel):
    answer: str
    tool_calls: list[ToolCallRecord]
    trace_id: str
    rounds: int
```

### 2.3 工具签名（全部同步函数，返回 `str` JSON）
```
query_snapshot(start_time: str, end_time: str, car_no: str = "", limit: int = 20) -> str
group_stats(table: Literal["snapshot","fee","trail"], group_by: str,
            start_time: str, end_time: str, top_n: int = 10) -> str
submit_export(table: Literal["snapshot","fee","trail"], start_time: str,
              end_time: str, mode: Literal["display","full"] = "display") -> str
export_status(task_id: str) -> str
es_status() -> str
```
统一返回 JSON 字符串：`{"ok": true, "data": ...}` 或 `{"ok": false, "error": "..."}`。
`@tool` 的 docstring 必须中文 + 英文各一句（方便 Java 开发理解）。

### 2.4 Graph
```python
def build_graph(checkpointer: Any = None) -> CompiledStateGraph:
    workflow = StateGraph(AgentState)
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", ToolNode(TOOLS))
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges("agent", should_continue,
                                   {"tools": "tools", "__end__": END})
    workflow.add_edge("tools", "agent")
    return workflow.compile(checkpointer=checkpointer)
```
`should_continue(state) -> Literal["tools", "__end__"]`：
- `state.get("error")` 非空 → `__end__`
- 最后一条 AIMessage 有 `tool_calls` 且 `tool_calls_count < max_rounds` → `tools`
- 否则 → `__end__`

`call_model(state)`:
- 调 LLM（绑定 TOOLS），捕获异常写 `state["error"]`；
- 每轮 `tool_calls_count` 从 state 读取并 +1 回写（用普通赋值，非 add_messages）。

### 2.5 API
```
POST /ai/agent/query
  body: AgentQueryRequest
  auth: Bearer token（复用现有依赖）
  response: AgentQueryResponse（HTTP 200）
  错误: LLM 不可用 → HTTP 503 + {"detail": "AI agent unavailable"}
```
实现：从 request 提取 token → `build_graph(InMemorySaver())` →
`graph.invoke({"messages":[HumanMessage(question)], "trace_id": uuid4().hex,
"tool_calls_count":0, "error":None}, config={"configurable":{"thread_id": session_id or trace_id}})` →
从 final AIMessage 取 content → 收集 ToolMessage 构造 `tool_calls` 列表。

## 3. 依赖变更（`pyproject.toml` + `requirements-ai.txt`）
```
langchain>=1.5,<2.0
langchain-openai>=1.8,<2.0
langgraph>=1.0,<2.0
pydantic>=2.7,<3.0
```
新增 `requirements-ai.txt`（只列 AI 依赖，CI 增量安装）；不动 `requirements.txt` 主清单。
`[project.optional-dependencies] ai = [...]`。

## 4. CI/CD 规格
新增 `.github/workflows/ai-agent-e2e.yml`：
- `workflow_dispatch` + `push` 到 `ai-agent-langgraph` 分支触发；
- job `e2e`：ubuntu-latest，Python 3.12，装 `requirements.txt` + `requirements-ai.txt`；
- 运行 `pytest tests/ai_agent -q --cov=app/ai_agent --cov-fail-under=70`；
- 运行健康检查脚本 `tools/ai_agent_smoke.py`（启动 FastAPI + 真实 HTTP 调用 `/ai/agent/query`，
  使用 FakeModel 无需外部 key）；
- 不用 workflow/job 级 env 放任何密钥（GitHub Actions 会回显）。

## 5. 验收标准（DoD）
- [ ] `pytest tests/ai_agent -q` 全绿，覆盖率 ≥70%
- [ ] `check_routes.py` 仍 29 controller / 110 route（AI 路由独立）
- [ ] 云 runner e2e workflow success
- [ ] 设计/spec 经独立会话审阅通过
- [ ] 两个分支的异同一致性说明文档完成
