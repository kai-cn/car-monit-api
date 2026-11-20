# Spec 修订补充 · LangChain 专属 — 审阅后定稿

> 本文件与 `AI-AGENT-SPEC-ADDENDUM.md`（共用修订）一起，**覆盖**原 DESIGN/SPEC 冲突条款。

## L1（关闭 B4）LangChain `state_schema` 与可观测字段

```python
from langchain.agents import AgentState, create_agent
from typing import TypedDict, Any

class AgentRuntimeState(AgentState):
    trace_id: str
    rounds: int
    tool_records: list[dict[str, Any]]

agent = create_agent(
    model=_build_model(), tools=TOOLS, system_prompt=SYSTEM_PROMPT,
    response_format=AgentAnswer, state_schema=AgentRuntimeState,
    middleware=[TraceMiddleware()], checkpointer=get_checkpointer(),
)
```
`TraceMiddleware.after_agent(state, runtime)` 返回
`{"rounds": state.get("rounds",0), "tool_records": list(self._buffer)}`，
确保 `invoke()` 结果里能读到 `rounds` / `tool_records` / `structured_response`。

## L2（关闭 B5）循环保护等价实现

`recursion_limit = settings.max_rounds * 2 + 2` 传入 `agent.invoke(..., config={"recursion_limit":...,
"configurable":{"thread_id":...}})`；超限抛 `GraphRecursionError` → API 层捕获 → 503。
`wrap_tool_call` 内累加 `rounds`，超过 `max_rounds` 直接返回
`ToolMessage(content='{"ok":false,"error":"round_limit"}')` 不再调真工具。

## L3（关闭 B3）会话单例

```python
_AGENT: Any = None
_CHECKPOINTER: Any = None

def get_agent() -> Any:
    global _AGENT, _CHECKPOINTER
    if _AGENT is None:
        _CHECKPOINTER = InMemorySaver()
        _AGENT = build_agent(checkpointer=_CHECKPOINTER)
    return _AGENT
```
与 LangGraph 分支 `get_graph()` 同为进程级单例，语义对等。

## L4（关闭 B1/B2）鉴权与错误体
完全采用共用 ADDENDUM 的 R1/R2（`AI_AGENT_ACCESS_TOKEN` fail-closed + Spring 错误体）。

## L5（关闭 B6）隐私
工具层脱敏与确认流程采用共用 ADDENDUM 的 R4；middleware 的 `result_preview` 只记白名单键。

## L6（关闭 B7）Service 映射
采用共用 ADDENDUM 的 R5 同一张映射表。

## L7（关闭 B8）技术表述
LangChain 分支无 `create_react_agent` 表述错误；补充：`create_agent` 底层即 LangGraph，
因此两个分支共享 `langgraph` 依赖，但**编排写法不同**（显式 StateGraph vs 声明式 middleware）。

## L8 跨分支一致性
trace_id/rounds/tool_calls 来源与共用 ADDENDUM R7 一致；
`AgentAnswer.confidence` → `AgentQueryResponse` 暂不新增字段（保持两分支响应字段完全一致），
confidence 仅记入 trace 日志；`sources` 用于交叉校验 `tool_calls[].name`。
