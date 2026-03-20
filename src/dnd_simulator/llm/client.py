"""LLM client for NPC dialog via OpenRouter."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageFunctionToolCall

logger = logging.getLogger("dnd_simulator.llm")


@dataclass(frozen=True)
class ToolCall:
    """A single tool invocation returned by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class LlmResponse:
    """Result of an LLM generation that may include tool calls."""

    text: str | None
    tool_call: ToolCall | None
    raw_message: object  # original ChatCompletionMessage for context threading

    @property
    def is_tool_call(self) -> bool:
        return self.tool_call is not None


def _parse_tool_call(tc: ChatCompletionMessageFunctionToolCall) -> ToolCall:
    import json

    return ToolCall(
        id=tc.id,
        name=tc.function.name,
        arguments=json.loads(tc.function.arguments),
    )


class LlmClient:
    """Thin wrapper around OpenAI-compatible API (OpenRouter)."""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek/deepseek-chat-v3-0324",
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def generate_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        max_tokens: int = 200,
        temperature: float = 0.8,
    ) -> LlmResponse:
        """Generate a completion that may include a tool call."""
        # Extract caller context from system message
        caller = "?"
        for m in messages:
            if m.get("role") == "system":
                content = str(m.get("content", ""))
                first_line = content.split("\n")[0][:80]
                caller = first_line
                break

        tool_names = []
        for t in tools:
            func = t.get("function")
            tool_names.append(func["name"] if isinstance(func, dict) else "?")
        logger.info("[LLM] %s | tools: %s", caller, tool_names)

        t0 = time.monotonic()
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            tools=tools,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
        )
        elapsed_ms = (time.monotonic() - t0) * 1000

        msg = response.choices[0].message
        tool_call = None
        if msg.tool_calls:
            raw_tc = msg.tool_calls[0]
            if isinstance(raw_tc, ChatCompletionMessageFunctionToolCall):
                tool_call = _parse_tool_call(raw_tc)

        usage = response.usage
        tokens_info = ""
        if usage:
            tokens_info = f" | tokens: {usage.prompt_tokens}→{usage.completion_tokens}"

        if tool_call:
            logger.info(
                "[LLM] → tool: %s(%s) | %.0fms%s",
                tool_call.name,
                _compact_args(tool_call.arguments),
                elapsed_ms,
                tokens_info,
            )
        else:
            text_preview = (msg.content or "")[:80].replace("\n", " ")
            logger.info("[LLM] → text: \"%s\" | %.0fms%s", text_preview, elapsed_ms, tokens_info)

        return LlmResponse(
            text=msg.content,
            tool_call=tool_call,
            raw_message=msg,
        )


def _compact_args(args: dict[str, Any]) -> str:
    """Format tool call arguments compactly for logging."""
    parts = []
    for k, v in args.items():
        val = str(v)
        if len(val) > 50:
            val = val[:47] + "..."
        parts.append(f"{k}={val}")
    return ", ".join(parts)
