# Spec 修订补充（LangGraph 分支）— 审阅后定稿

> 本文件**覆盖** `AI-AGENT-DESIGN.md` / `AI-AGENT-SPEC.md` 中与本文冲突的条款。
> 来源：独立只读审阅会话 2026-11-21 的 8 项 BLOCKED 结论，逐项关闭。

## R1（关闭 B1）鉴权：没有 Spring Security，用显式 API Key 守卫

**事实**：本 Python 项目无 `fastapi.security` / Bearer 依赖；`internal_guard` 只覆盖 `/api/v3/**` 等前缀。
**决策**：`/ai/agent/**` 用**独立 API Key 守卫**（不扩展 internal_guard，避免混淆两个体系）：

```python
# app/ai_agent/auth.py
def verify_agent_key(x_agent_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("AI_AGENT_API_KEY")   # 复用同一个 env 名？不——见下
```

**不能复用 `AI_AGENT_API_KEY`（那是 LLM key）**。改用新变量：

| 变量 | 默认 | 说明 |
|---|---|---|
| `AI_AGENT_ACCESS_TOKEN` | (空) | Agent 端点访问令牌；空 = **拒绝所有请求**（fail-closed） |
| `AI_AGENT_API_KEY` | (空) | LLM 密钥；空 = FakeModel |

`verify_agent_key`：`expected` 为空 → 503（服务未配置，不静默开放）；非空用
`hmac.compare_digest` 常量时间比较；不匹配 → 403。响应体走项目全局 handler 的 Spring 形状
（抛 `StarletteHTTPException(403)` → `error_response(403, path)`）。

## R2（关闭 B2）错误契约：与全局 handler 对齐

| 场景 | HTTP | 响应体 |
|---|---|---|
| 参数校验失败 | 400 | `error_response(400, path)`（Spring 错误体，全局 handler 自动处理） |
| 无/错访问令牌 | 403 | `error_response(403, path)` |
| 服务未配置访问令牌 | 503 | `error_response(503, path)` |
| LLM 不可用 / `state.error` 非空 | 503 | `error_response(503, path)`，不返回 200 空答案 |
| 正常 | 200 | `AgentQueryResponse` |

API 层显式检查 `state["error"]`，非空则 `raise StarletteHTTPException(503)`。

## R3（关闭 B3）会话记忆：进程级单例

```python
# app/ai_agent/graph.py
_CHECKPOINTER: InMemorySaver | None = None
_GRAPH: Any = None

def get_graph() -> Any:
    global _CHECKPOINTER, _GRAPH
    if _GRAPH is None:
        _CHECKPOINTER = InMemorySaver()
        _GRAPH = build_graph(checkpointer=_CHECKPOINTER)
    return _GRAPH
```
API 用 `get_graph()`（单例），`thread_id = session_id or trace_id`。
**清理策略**：`InMemorySaver` 进程重启即清空；文档声明"仅开发/单实例可用，生产换 PostgresSaver"。

## R4（关闭 B6）隐私/数据最小化

1. `query_snapshot` 的 `car_no` 入参在工具内**掩码**：只保留前 3 位 + `***`（如 `赣A5***`），
   返回数据只含 `count` / `time_bucket` / `section_code`，**不返回原始车牌/轨迹明细**；
2. `ToolCallRecord.result_preview` 只留工具返回 JSON 的 `ok`/`count`/`taskId` 等白名单键，
   **禁止**把完整 tool message 放进响应；
3. `submit_export` 需要确认：Agent 第一次调用返回 `{"ok": false, "need_confirm": true, "confirm_token": <uuid>}`，
   API 暴露 `POST /ai/agent/confirm`（带 `confirm_token`）才真正提交；对应 LangGraph 的
   `interrupt` 语义（用 state 字段 `pending_confirm` 实现，不依赖 checkpoint 的 interrupt API，
   避免版本差异）；
4. checkpointer 保存的消息里不含原始 PII（工具返回已脱敏）。

## R5（关闭 B7）工具 → 真实 Service 映射（修正不存在的 `ExportV3Service`）

| 工具 | 真实调用 | 位置 |
|---|---|---|
| `query_snapshot` | `TrafficSearchService.search(TrafficSearchRequest)` | `.../service/v3/v3_services.py:327,337` |
| `group_stats` | `BigScreenStatsService.warning_top(start_time, end_time, top_n)`（真实符号；返回 `List[Dict]`） | 同文件 `:517,529` |
| `submit_export` | `ExportTaskService.submit_display(ExportRequest)` / `submit_full` | 同文件 `:184,216,219` |
| `export_status` | `ExportTaskService.get(task_id) -> Optional[ExportTask]`（**不是** `status`） | 同文件 `:235` |
| `es_status` | `TrafficEsIndexService` 的状态查询 | 同文件 `:386` |

**降级**：Service 不可用（import 失败/未初始化）时工具返回 `{"ok": false, "error": "service_unavailable"}`,
不抛异常进 Agent。

## R6（关闭 B8）技术表述更正

DESIGN §3.1 改为："LangGraph v1 仍提供 `create_react_agent`（`langgraph.prebuilt`），
但官方推荐新项目用 LangChain v1 `create_agent`；本分支**刻意采用 StateGraph 显式编排**
以展示可控工作流，不是因为该 API 被弃用。"

## R7（关闭 B4/B5 的跨分支一致性）对外契约一致的具体办法

- `trace_id` 由 **API 层生成**（`uuid4().hex`），放入 state 与 `config["configurable"]["thread_id"]`，
  不依赖 graph 内部生成；
- `rounds` 由 API 层数 `ToolMessage` 数量 / 工具轮次（state 里累加），两分支 alike；
- LangGraph：state 字段 `tool_calls_count`；LangChain：`state_schema=AgentRuntimeState` 自定义
  TypedDict（含 `trace_id` / `rounds` / `tool_records`），middleware 的 `after_agent` 返回
  `{"rounds":..., "tool_records":...}` 更新，**确保 invoke 结果可见**；
- 两分支都用 `recursion_limit = max_rounds * 2 + 2` 作为硬上限（LangChain 等价循环保护）。

## R8（非阻断项落地）
- `SYSTEM_PROMPT` 提为模块级常量，写入 `tools.py` 或 `agent.py/graph.py` 导出清单；
- `FakeAgentModel` 构造签名：`FakeAgentModel(responses: list[str] | list[AIMessage])`，按 invoke 次数出队；
- `AI_AGENT_TIMEOUT_SEC` 用于 `ChatOpenAI(timeout=...)`；
- 请求字段 `tables` 用于过滤 `TOOLS` 白名单（snapshot/fee/trail 对应 tool 子集）；
- `MAX_TOOL_ROUNDS` 唯一来源 = `settings.max_rounds`（环境变量），常量只作默认值；
- `tools/ai_agent_smoke.py` 列入文件清单；
- LangChain `AgentAnswer.confidence/sources` 映射进 `AgentQueryResponse`
  （`answer` 用 AgentAnswer.answer，`tool_calls[].name` 用 sources 交叉校验）；
  **跨分支最终裁定**：`AgentQueryResponse` 不新增 confidence 字段，
  `confidence` 仅记入 trace 日志，两分支响应字段完全一致（以 LangChain 专属
  ADDENDUM L8 为准）。

## 审阅复结论
以上 R1–R8 关闭 8 项 BLOCKED。实现必须同时遵守原 SPEC 与本文；冲突以本文为准。
