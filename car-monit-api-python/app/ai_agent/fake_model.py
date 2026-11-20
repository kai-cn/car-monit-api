# -*- coding: utf-8 -*-
"""测试用 LLM（FakeAgentModel）—— 支持 tool_calls 序列。

LangChain 官方 ``FakeListChatModel`` 只返回字符串，无法让 Agent 真正调用工具。
本类继承 ``SimpleChatModel``（官方测试基类），覆盖 ``_generate`` 返回带
``tool_calls`` 的 ``AIMessage``，这样 LangGraph/LangChain 的 agent 循环会按官方路径执行。

【Java 对照】JUnit ``@MockBean ChatModel`` 的 thenReturn 序列。
"""
from __future__ import annotations

from typing import Any, Iterator, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import SimpleChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeAgentModel(SimpleChatModel):
    """按预定序列返回 AIMessage（可含 tool_calls）的假模型。

    ``responses`` 每项可以是：
    * ``str`` → AIMessage(content=字符串)
    * ``AIMessage`` → 原样返回（用于注入 tool_calls）
    """

    responses: list[Any]
    i: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake-agent-model"

    def bind_tools(self, tools, **kwargs):
        """FakeModel 无需按工具 schema 生成调用；直接返回自身供 Agent 循环调用。

        Java 对照：mock 的 ``when(chatModel.bindTools(any()))`` 返回 mock 自身。
        测试如需要 tool_calls，直接把 ``AIMessage(tool_calls=[...])`` 放进 responses。
        """
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        item = self.responses[self.i % len(self.responses)]
        self.i += 1
        msg = item if isinstance(item, AIMessage) else AIMessage(content=str(item))
        return ChatResult(generations=[ChatGeneration(message=msg)])

    def _call(self, *args: Any, **kwargs: Any) -> str:
        item = self.responses[self.i % len(self.responses)]
        self.i += 1
        return item if isinstance(item, str) else str(getattr(item, "content", ""))
