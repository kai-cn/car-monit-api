#!/usr/bin/env python3
"""OpenAI 兼容的**假模型**，用于 Agent E2E（不消耗真实 token、不依赖外网）。

用途
----
E2E 需要验证的是"我方链路"：SSE 契约、工具调用、鉴权、限流、会话清理。
模型回答的质量不是被测对象，因此这里用确定性桩件替代真模型：

1. 第一次请求（对话里还没有工具结果）且用户提到"查/轨迹/指标/质量/知识" → 返回 `tool_call`；
2. 第二次请求（对话里已有 `role=tool` 的消息） → 把工具结果摘要成一段文本返回。

两分支（Spring AI / AgentScope）都通过 HTTP 调用本服务，因此同一份桩件可复用。

接口
----
- `POST /v1/chat/completions`：支持 `stream=true|false`（SSE）
- `GET  /v1/models`：部分客户端启动时会探测
- `GET  /health`：探活

运行
----
    python3 scripts/agent/mock_llm.py --port 18080

可选 `--record /tmp/mock-llm.jsonl`：把每次请求体落盘，便于 CI 断言"模型确实被调了 2 次"。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

TOOL_HINTS = {
    "get_vehicle_track": ("轨迹", "路径", "回放"),
    "get_bigscreen_metric": ("指标", "大屏", "总量", "统计"),
    "get_data_quality": ("质量", "缺失", "延迟", "断点"),
    "search_knowledge": ("口径", "怎么算", "是什么", "表结构", "字段", "为什么"),
}

DEFAULT_TOOL = "query_traffic_records"


def _user_text(messages: list[dict[str, Any]]) -> str:
    parts = []
    for message in messages:
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        parts.append(block.get("text") or "")
    return "".join(parts)


def _tool_result_text(messages: list[dict[str, Any]]) -> str | None:
    """取**本轮**的工具结果。

    只认"最后一条消息是 role=tool"：历史里可能残留上一轮的工具结果，
    若扫全表会让第二轮对话误以为"已经查完了"，从而跳过工具调用。
    真实模型靠上下文语义判断，桩件用位置判断更稳。
    """
    if not messages:
        return None
    last = messages[-1]
    if last.get("role") != "tool":
        return None
    content = last.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b.get("text") or "" for b in content if isinstance(b, dict))
    return None


def _pick_tool(text: str) -> str:
    for name, hints in TOOL_HINTS.items():
        if any(hint in text for hint in hints):
            return name
    return DEFAULT_TOOL


def _tool_arguments(name: str, text: str) -> dict[str, Any]:
    now = int(time.time())
    if name == "get_vehicle_track":
        plate = _plate(text) or "赣B21E85"
        return {"plate": plate, "start_time": _fmt(now - 6 * 3600), "end_time": _fmt(now)}
    if name == "get_bigscreen_metric":
        return {"metric": "income", "start_time": _fmt(now - 86400), "end_time": _fmt(now)}
    if name == "get_data_quality":
        return {"start_time": _fmt(now - 3600), "end_time": _fmt(now)}
    if name == "search_knowledge":
        return {"query": text[:40] or "指标口径"}
    return {
        "table": "fee",
        "plate": _plate(text) or "赣B21E85",
        "start_time": _fmt(now - 86400),
        "end_time": _fmt(now),
        "page_size": 5,
    }


def _plate(text: str) -> str | None:
    match = re.search(r"[\u4e00-\u9fa5][A-Z][A-Z0-9]{4,6}", text)
    return match.group(0) if match else None


def _fmt(epoch: int) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(epoch))


def _summary(tool_text: str) -> str:
    """把工具 JSON 压成一句人话，模拟模型的"读结果后作答"。"""
    try:
        payload = json.loads(tool_text)
    except Exception:
        return "工具已返回结果，但内容不是合法 JSON。"
    if payload.get("ok") is False:
        return f"查询未成功：{payload.get('errorCode')}（{payload.get('message')}）。可以缩小时间范围后重试。"
    total = payload.get("total")
    rows = payload.get("rows") or payload.get("points") or payload.get("items") or []
    if isinstance(total, int):
        return f"共匹配到 {total} 条记录，下面展示其中 {len(rows)} 条。"
    if isinstance(rows, list) and rows:
        return f"返回 {len(rows)} 条数据。"
    for key in ("value", "answer", "content", "summary"):
        if payload.get(key):
            return str(payload[key])[:120]
    return "已按你的条件完成查询，未发现异常。"


def plan(messages: list[dict[str, Any]]) -> tuple[str, Any]:
    """返回 ("tool", (name, args_json)) 或 ("text", 文本)。"""
    tool_text = _tool_result_text(messages)
    if tool_text is not None:
        return "text", _summary(tool_text)
    text = _user_text(messages)
    name = _pick_tool(text)
    if name == DEFAULT_TOOL and not any(k in text for k in ("查", "记录", "流水", "通行", "收费")):
        # 纯闲聊/知识问题：不调工具，直接答，覆盖"无工具轮次"路径
        if "知识" not in text and "口径" not in text and "是什么" not in text:
            return "text", "我是路网数据助手，可以帮你查通行记录、回放轨迹、看指标或数据质量。"
    return "tool", (name, json.dumps(_tool_arguments(name, text), ensure_ascii=False))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "mock-llm/1.0"

    # ---- 路由 ----
    def do_GET(self) -> None:  # noqa: N802 (http.server 约定)
        if self.path.startswith("/health"):
            self._json(200, {"status": "UP"})
        elif self.path.startswith("/v1/models"):
            self._json(200, {"object": "list", "data": [{"id": self.server.model, "object": "model"}]})
        else:
            self._json(404, {"error": {"message": "not found"}})

    def do_POST(self) -> None:  # noqa: N802
        if not self.path.startswith("/v1/chat/completions"):
            self._json(404, {"error": {"message": "not found"}})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw)
        except Exception:
            self._json(400, {"error": {"message": "invalid json"}})
            return

        self._record(raw)
        messages = body.get("messages") or []
        kind, payload = plan(messages)
        model = body.get("model") or self.server.model
        if body.get("stream"):
            self._stream(model, kind, payload)
        else:
            self._complete(model, kind, payload)

    # ---- 响应 ----
    def _complete(self, model: str, kind: str, payload: Any) -> None:
        message: dict[str, Any] = {"role": "assistant", "content": None}
        finish = "stop"
        if kind == "tool":
            name, args = payload
            message["tool_calls"] = [{
                "id": "call_mock_1", "type": "function",
                "function": {"name": name, "arguments": args},
            }]
            finish = "tool_calls"
        else:
            message["content"] = payload
        self._json(200, {
            "id": "chatcmpl-mock", "object": "chat.completion", "created": int(time.time()),
            "model": model,
            "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 128, "completion_tokens": 32, "total_tokens": 160},
        })

    def _stream(self, model: str, kind: str, payload: Any) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        base = {"id": "chatcmpl-mock", "object": "chat.completion.chunk",
                "created": int(time.time()), "model": model}

        def chunk(delta: dict[str, Any], finish: str | None = None) -> None:
            frame = dict(base)
            frame["choices"] = [{"index": 0, "delta": delta, "finish_reason": finish}]
            self._write(f"data: {json.dumps(frame, ensure_ascii=False)}\n\n")

        chunk({"role": "assistant", "content": ""})
        if kind == "tool":
            name, args = payload
            chunk({"tool_calls": [{
                "index": 0, "id": "call_mock_1", "type": "function",
                "function": {"name": name, "arguments": args},
            }]})
            chunk({}, "tool_calls")
            # 有些客户端要求 usage 只在末尾帧携带
            frame = dict(base)
            frame["choices"] = []
            frame["usage"] = {"prompt_tokens": 128, "completion_tokens": 32, "total_tokens": 160}
            self._write(f"data: {json.dumps(frame, ensure_ascii=False)}\n\n")
        else:
            # 逐片输出，模拟真实流式；10ms 间隔让前端能看出"打字机效果"
            text = str(payload)
            for i in range(0, len(text), 8):
                chunk({"content": text[i:i + 8]})
                time.sleep(0.01)
            chunk({}, "stop")
            frame = dict(base)
            frame["choices"] = []
            frame["usage"] = {"prompt_tokens": 160, "completion_tokens": max(1, len(text) // 2),
                              "total_tokens": 160 + max(1, len(text) // 2)}
            self._write(f"data: {json.dumps(frame, ensure_ascii=False)}\n\n")
        self._write("data: [DONE]\n\n")

    def _write(self, text: str) -> None:
        self.wfile.write(text.encode("utf-8"))
        self.wfile.flush()

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _record(self, raw: bytes) -> None:
        path = self.server.record_path
        if not path:
            return
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(raw.decode("utf-8", "replace").replace("\n", " ") + "\n")
        except Exception as exc:  # 记录失败不影响主流程
            print(f"[mock-llm] record failed: {exc}", file=sys.stderr)

    def log_message(self, fmt: str, *args: Any) -> None:  # 降噪
        if "--verbose" in sys.argv:
            super().log_message(fmt, *args)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18080)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--model", default="mock-model")
    parser.add_argument("--record", default="")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.model = args.model           # type: ignore[attr-defined]
    server.record_path = args.record    # type: ignore[attr-defined]
    print(f"[mock-llm] listening on http://{args.host}:{args.port} model={args.model}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
