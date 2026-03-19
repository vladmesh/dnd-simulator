"""LLM client for NPC dialog via OpenRouter."""

from __future__ import annotations

from openai import OpenAI


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

    def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 200,
        temperature: float = 0.8,
    ) -> str:
        """Generate a chat completion."""
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
            temperature=temperature,
        )
        choice = response.choices[0]
        return choice.message.content or ""
