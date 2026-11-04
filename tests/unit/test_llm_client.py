"""Unit tests for the OpenRouter LLM client wrapper (no network: the OpenAI SDK client is faked)."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
import structlog
from openai.types.chat import (
    ChatCompletionFunctionToolParam,
    ChatCompletionMessage,
    ChatCompletionMessageCustomToolCall,
    ChatCompletionMessageFunctionToolCall,
    ChatCompletionMessageParam,
)
from openai.types.chat.chat_completion_message_custom_tool_call import Custom
from openai.types.chat.chat_completion_message_function_tool_call import Function
from openai.types.completion_usage import CompletionUsage

import dnd_simulator.llm.client as client_module
from dnd_simulator.llm.client import LlmClient, LlmResponse, ToolCall

MESSAGES: list[ChatCompletionMessageParam] = [
    {"role": "system", "content": "You are an NPC."},
    {"role": "user", "content": "Your turn."},
]


def _tool(name: str) -> ChatCompletionFunctionToolParam:
    return {"type": "function", "function": {"name": name, "parameters": {"type": "object", "properties": {}}}}


@dataclass
class _Choice:
    message: ChatCompletionMessage


@dataclass
class _Completion:
    choices: list[_Choice]
    usage: object


@dataclass
class _FakeCompletions:
    owner: _FakeOpenAI

    def create(self, **kwargs: object) -> _Completion:
        self.owner.calls.append(kwargs)
        if self.owner.error is not None:
            raise self.owner.error
        assert self.owner.response is not None
        return self.owner.response


@dataclass
class _FakeChat:
    completions: _FakeCompletions


@dataclass
class _FakeOpenAI:
    """Stand-in for ``openai.OpenAI`` that records constructor args, options and create() calls."""

    init_kwargs: dict[str, object] = field(default_factory=dict)
    options: list[dict[str, object]] = field(default_factory=list)
    calls: list[dict[str, object]] = field(default_factory=list)
    response: _Completion | None = None
    error: Exception | None = None
    root: _FakeOpenAI | None = None

    @property
    def chat(self) -> _FakeChat:
        return _FakeChat(_FakeCompletions(self.root or self))

    def with_options(self, **kwargs: object) -> _FakeOpenAI:
        root = self.root or self
        root.options.append(kwargs)
        return _FakeOpenAI(root=root)


@pytest.fixture
def fake_openai(monkeypatch: pytest.MonkeyPatch) -> Iterator[_FakeOpenAI]:
    fake = _FakeOpenAI()

    def factory(**kwargs: object) -> _FakeOpenAI:
        fake.init_kwargs = kwargs
        return fake

    monkeypatch.setattr(client_module, "OpenAI", factory)
    # Deterministic elapsed time: each call reads monotonic twice (start/end) -> 1.25 s apart.
    ticks = iter([10.0, 11.25] * 10)
    # The suite runs at WARNING; capture info/debug records too (conftest restores the config).
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.DEBUG))
    monkeypatch.setattr(client_module.time, "monotonic", lambda: next(ticks))
    yield fake


def _completion(
    content: str | None = None,
    tool_calls: list[Any] | None = None,
    usage: object = None,
) -> _Completion:
    message = ChatCompletionMessage(role="assistant", content=content, tool_calls=tool_calls)
    return _Completion(choices=[_Choice(message)], usage=usage)


def _function_call(name: str, arguments: str, call_id: str = "call_1") -> ChatCompletionMessageFunctionToolCall:
    return ChatCompletionMessageFunctionToolCall(
        id=call_id, type="function", function=Function(name=name, arguments=arguments)
    )


class TestConstruction:
    def test_default_base_url_is_openrouter(self, fake_openai: _FakeOpenAI) -> None:
        LlmClient(api_key="test-key", model="test/model")

        assert fake_openai.init_kwargs == {"api_key": "test-key", "base_url": "https://openrouter.ai/api/v1"}

    def test_custom_base_url(self, fake_openai: _FakeOpenAI) -> None:
        LlmClient(api_key="k", model="m", base_url="http://localhost:9999/v1")

        assert fake_openai.init_kwargs["base_url"] == "http://localhost:9999/v1"


class TestGenerate:
    def test_builds_request_and_returns_text(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="Hello, traveller.")
        llm = LlmClient(api_key="k", model="test/model")

        text = llm.generate(MESSAGES, max_tokens=123, temperature=0.1)

        assert text == "Hello, traveller."
        assert fake_openai.calls == [
            {"model": "test/model", "messages": MESSAGES, "max_tokens": 123, "temperature": 0.1}
        ]
        assert fake_openai.options == []

    def test_default_sampling_parameters(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="x")

        LlmClient(api_key="k", model="m").generate(MESSAGES)

        assert fake_openai.calls[0]["max_tokens"] == 300
        assert fake_openai.calls[0]["temperature"] == 0.3

    def test_none_content_becomes_empty_string(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content=None)

        assert LlmClient(api_key="k", model="m").generate(MESSAGES) == ""

    def test_timeout_and_max_retries_are_applied_as_client_options(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="ok")

        LlmClient(api_key="k", model="m").generate(MESSAGES, timeout=2.5, max_retries=0)

        assert fake_openai.options == [{"timeout": 2.5}, {"max_retries": 0}]
        assert len(fake_openai.calls) == 1

    def test_only_timeout_option(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="ok")

        LlmClient(api_key="k", model="m").generate(MESSAGES, timeout=7.0)

        assert fake_openai.options == [{"timeout": 7.0}]

    def test_only_max_retries_option(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="ok")

        LlmClient(api_key="k", model="m").generate(MESSAGES, max_retries=3)

        assert fake_openai.options == [{"max_retries": 3}]

    def test_logs_response_with_usage(self, fake_openai: _FakeOpenAI) -> None:
        usage = CompletionUsage(prompt_tokens=40, completion_tokens=12, total_tokens=52)
        fake_openai.response = _completion(content="ok", usage=usage)

        with structlog.testing.capture_logs() as logs:
            LlmClient(api_key="k", model="m").generate(MESSAGES)

        assert logs == [
            {
                "event": "llm_response",
                "log_level": "info",
                "domain": "llm",
                "caller": "inner_self_digest",
                "elapsed_ms": 1250,
                "tokens_in": 40,
                "tokens_out": 12,
            }
        ]

    def test_logs_response_without_usage(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="ok", usage=None)

        with structlog.testing.capture_logs() as logs:
            LlmClient(api_key="k", model="m").generate(MESSAGES)

        assert "tokens_in" not in logs[0]
        assert "tokens_out" not in logs[0]

    def test_partial_usage_logs_only_present_counts(self, fake_openai: _FakeOpenAI) -> None:
        @dataclass
        class _PartialUsage:
            prompt_tokens: int | None = None
            completion_tokens: int | None = None

        fake_openai.response = _completion(content="ok", usage=_PartialUsage(prompt_tokens=5))

        with structlog.testing.capture_logs() as logs:
            LlmClient(api_key="k", model="m").generate(MESSAGES)

        assert logs[0]["tokens_in"] == 5
        assert "tokens_out" not in logs[0]

    def test_error_is_logged_and_reraised(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.error = TimeoutError("request timed out")
        llm = LlmClient(api_key="k", model="m")

        with structlog.testing.capture_logs() as logs, pytest.raises(TimeoutError, match="request timed out"):
            llm.generate(MESSAGES, timeout=1.0, max_retries=0)

        assert logs == [
            {
                "event": "llm_error",
                "log_level": "error",
                "domain": "llm",
                "caller": "inner_self_digest",
                "elapsed_ms": 1250,
            }
        ]


class TestGenerateWithTools:
    def test_builds_request_with_tools(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="thinking")
        tools = [_tool("attack"), _tool("end_turn")]

        LlmClient(api_key="k", model="test/model").generate_with_tools(MESSAGES, tools, max_tokens=50, temperature=0.0)

        assert fake_openai.calls == [
            {"model": "test/model", "messages": MESSAGES, "tools": tools, "max_tokens": 50, "temperature": 0.0}
        ]

    def test_default_sampling_parameters(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="x")

        LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("idle")])

        assert fake_openai.calls[0]["max_tokens"] == 700
        assert fake_openai.calls[0]["temperature"] == 0.8

    def test_parses_function_tool_call(self, fake_openai: _FakeOpenAI) -> None:
        raw = _function_call("attack", json.dumps({"target_id": "goblin_1", "weapon": "sword"}), call_id="c42")
        fake_openai.response = _completion(content=None, tool_calls=[raw])

        response = LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("attack")])

        assert isinstance(response, LlmResponse)
        assert response.is_tool_call
        assert response.tool_call == ToolCall(
            id="c42", name="attack", arguments={"target_id": "goblin_1", "weapon": "sword"}
        )
        assert response.text is None
        assert response.raw_message is fake_openai.response.choices[0].message

    def test_only_first_tool_call_is_used(self, fake_openai: _FakeOpenAI) -> None:
        first = _function_call("dodge", "{}", call_id="a")
        second = _function_call("attack", '{"target_id": "x"}', call_id="b")
        fake_openai.response = _completion(tool_calls=[first, second])

        response = LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("dodge")])

        assert response.tool_call == ToolCall(id="a", name="dodge", arguments={})

    def test_invalid_json_arguments_raise(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(tool_calls=[_function_call("attack", "{not json")])

        with pytest.raises(json.JSONDecodeError):
            LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("attack")])

    def test_non_function_tool_call_is_ignored(self, fake_openai: _FakeOpenAI) -> None:
        custom = ChatCompletionMessageCustomToolCall(
            id="c1", type="custom", custom=Custom(name="freeform", input="raw")
        )
        fake_openai.response = _completion(content="fallback text", tool_calls=[custom])

        response = LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("attack")])

        assert not response.is_tool_call
        assert response.tool_call is None
        assert response.text == "fallback text"

    def test_text_response_without_tool_calls(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="I shall wait.", tool_calls=[])

        response = LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("attack")])

        assert not response.is_tool_call
        assert response.text == "I shall wait."

    def test_tool_call_logging(self, fake_openai: _FakeOpenAI) -> None:
        long_value = "a" * 60
        raw = _function_call("say", json.dumps({"text": long_value, "target_id": "npc_2"}))
        usage = CompletionUsage(prompt_tokens=100, completion_tokens=20, total_tokens=120)
        fake_openai.response = _completion(tool_calls=[raw], usage=usage)
        tools = [_tool("say"), _tool("end_turn")]

        with structlog.testing.capture_logs() as logs:
            LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, tools)

        events = [entry["event"] for entry in logs]
        assert events == ["llm_request", "llm_tool_call", "llm_full_context"]
        assert logs[0] == {"event": "llm_request", "log_level": "info", "domain": "llm", "tools": ["say", "end_turn"]}
        assert logs[1] == {
            "event": "llm_tool_call",
            "log_level": "info",
            "domain": "llm",
            "tool": "say",
            "args": f"text={'a' * 47}..., target_id=npc_2",
            "elapsed_ms": 1250,
            "tokens_in": 100,
            "tokens_out": 20,
        }
        assert logs[2] == {
            "event": "llm_full_context",
            "log_level": "debug",
            "domain": "llm.context",
            "messages": MESSAGES,
            "tools": tools,
            "response_tool": "say",
            "response_text": None,
            "elapsed_ms": 1250,
            "tokens_in": 100,
            "tokens_out": 20,
        }

    def test_compact_args_keeps_exactly_50_char_values(self, fake_openai: _FakeOpenAI) -> None:
        raw = _function_call("say", json.dumps({"text": "b" * 50}))
        fake_openai.response = _completion(tool_calls=[raw])

        with structlog.testing.capture_logs() as logs:
            LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("say")])

        assert logs[1]["args"] == f"text={'b' * 50}"

    def test_text_response_logging_previews_first_line_chars(self, fake_openai: _FakeOpenAI) -> None:
        content = "line one\nline two " + "z" * 100
        fake_openai.response = _completion(content=content, usage=None)

        with structlog.testing.capture_logs() as logs:
            LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("attack")])

        assert [entry["event"] for entry in logs] == ["llm_request", "llm_text_response", "llm_full_context"]
        assert logs[1] == {
            "event": "llm_text_response",
            "log_level": "info",
            "domain": "llm",
            "text_preview": content[:80].replace("\n", " "),
            "elapsed_ms": 1250,
        }
        assert len(logs[1]["text_preview"]) == 80
        assert logs[2]["response_tool"] is None
        assert logs[2]["response_text"] == content

    def test_empty_text_response_logs_empty_preview(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content=None)

        with structlog.testing.capture_logs() as logs:
            response = LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("attack")])

        assert response.text is None
        assert logs[1]["text_preview"] == ""

    def test_error_is_logged_and_reraised(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.error = ConnectionError("network down")

        with structlog.testing.capture_logs() as logs, pytest.raises(ConnectionError, match="network down"):
            LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("attack"), _tool("dodge")])

        assert logs == [
            {"event": "llm_request", "log_level": "info", "domain": "llm", "tools": ["attack", "dodge"]},
            {
                "event": "llm_error",
                "log_level": "error",
                "domain": "llm",
                "elapsed_ms": 1250,
                "tools": ["attack", "dodge"],
            },
        ]

    def test_generate_with_tools_never_applies_client_options(self, fake_openai: _FakeOpenAI) -> None:
        fake_openai.response = _completion(content="x")

        LlmClient(api_key="k", model="m").generate_with_tools(MESSAGES, [_tool("attack")])

        assert fake_openai.options == []


class TestLlmResponse:
    def test_is_tool_call_reflects_tool_call_presence(self) -> None:
        assert LlmResponse(text=None, tool_call=ToolCall(id="1", name="n", arguments={}), raw_message=None).is_tool_call
        assert not LlmResponse(text="hi", tool_call=None, raw_message=None).is_tool_call
