"""LLM client for NPC dialog via OpenRouter."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import structlog
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageFunctionToolCall

logger = structlog.get_logger(domain="llm")


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
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
    ) -> None:
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    def generate(
        self,
        messages: list[dict[str, object]],
        max_tokens: int = 300,
        temperature: float = 0.3,
    ) -> str:
        """Generate a plain text completion (no tools)."""
        t0 = time.monotonic()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception:
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.error("llm_error", caller="summarizer", elapsed_ms=round(elapsed_ms))
            raise
        elapsed_ms = (time.monotonic() - t0) * 1000

        msg = response.choices[0].message
        usage = response.usage

        text = msg.content or ""
        logger.info("llm_response", caller="summarizer", elapsed_ms=round(elapsed_ms), **_usage_kwargs(usage))
        return text

    def generate_with_tools(
        self,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        max_tokens: int = 200,
        temperature: float = 0.8,
    ) -> LlmResponse:
        """Generate a completion that may include a tool call."""
        tool_names = []
        for t in tools:
            func = t.get("function")
            tool_names.append(func["name"] if isinstance(func, dict) else "?")
        logger.info("llm_request", tools=tool_names)

        t0 = time.monotonic()
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                tools=tools,  # type: ignore[arg-type]
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception:
            elapsed_ms = (time.monotonic() - t0) * 1000
            logger.error("llm_error", elapsed_ms=round(elapsed_ms), tools=tool_names)
            raise
        elapsed_ms = (time.monotonic() - t0) * 1000

        msg = response.choices[0].message
        tool_call = None
        if msg.tool_calls:
            raw_tc = msg.tool_calls[0]
            if isinstance(raw_tc, ChatCompletionMessageFunctionToolCall):
                tool_call = _parse_tool_call(raw_tc)

        usage = response.usage

        if tool_call:
            logger.info(
                "llm_tool_call",
                tool=tool_call.name,
                args=_compact_args(tool_call.arguments),
                elapsed_ms=round(elapsed_ms),
                **_usage_kwargs(usage),
            )
        else:
            text_preview = (msg.content or "")[:80].replace("\n", " ")
            logger.info(
                "llm_text_response",
                text_preview=text_preview,
                elapsed_ms=round(elapsed_ms),
                **_usage_kwargs(usage),
            )

        # Log full context for file dispatch (debug only)
        logger.debug(
            "llm_full_context",
            domain="llm.context",
            messages=messages,
            tools=tools,
            response_tool=tool_call.name if tool_call else None,
            response_text=msg.content,
            elapsed_ms=round(elapsed_ms),
            **_usage_kwargs(usage),
        )

        return LlmResponse(
            text=msg.content,
            tool_call=tool_call,
            raw_message=msg,
        )


def _usage_kwargs(usage: object) -> dict[str, int]:
    """Extract token usage into kwargs for structured logging."""
    if usage is None:
        return {}
    tokens_in = getattr(usage, "prompt_tokens", None)
    tokens_out = getattr(usage, "completion_tokens", None)
    result: dict[str, int] = {}
    if tokens_in is not None:
        result["tokens_in"] = int(tokens_in)
    if tokens_out is not None:
        result["tokens_out"] = int(tokens_out)
    return result


def _compact_args(args: dict[str, Any]) -> str:
    """Format tool call arguments compactly for logging."""
    parts = []
    for k, v in args.items():
        val = str(v)
        if len(val) > 50:
            val = val[:47] + "..."
        parts.append(f"{k}={val}")
    return ", ".join(parts)
