"""End-to-end coverage for the manual live inner-self driver with a fake model."""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api import app as app_module
from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.llm.client import LlmResponse, ToolCall


def _load_driver() -> ModuleType:
    path = Path(__file__).parents[2] / "scripts" / "live_inner_self.py"
    spec = spec_from_file_location("live_inner_self_driver", path)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


live_inner_self = _load_driver()


class FakeLlmClient:
    """Fake the decision and make every digest use the rules fallback."""

    raise_decision = False

    def __init__(self, api_key: str, model: str) -> None:
        del api_key, model

    def generate_with_tools(self, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> LlmResponse:
        del messages, tools
        if self.raise_decision:
            raise TimeoutError("fake decision timeout")
        return LlmResponse(text="", tool_call=ToolCall("fake", "flee", {}), raw_message=object())

    def generate(self, *args: object, **kwargs: object) -> str:
        del args, kwargs
        raise TimeoutError("fake digest timeout")


@dataclass
class _TestSocket:
    session: object
    manager: object

    def send(self, payload: str) -> None:
        self.session.send_text(payload)  # type: ignore[union-attr]

    def recv(self) -> str:
        return json.dumps(self.session.receive_json())  # type: ignore[union-attr]

    def close(self) -> None:
        self.manager.__exit__(None, None, None)  # type: ignore[union-attr]


class ScenarioTestTransport:
    def __init__(self, client: TestClient) -> None:
        self.client = client
        self.snapshot_sessions: list[str] = []

    def request(self, method: str, path: str, body: object | None = None) -> dict[str, object]:
        response = self.client.request(method.upper(), path, json=body)
        if not response.is_success:
            raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {response.json()}")
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError(f"{method} {path}: expected JSON object")
        if path.endswith("/inner-self"):
            session_id = path.split("/")[4]
            get_service().get_session(session_id)
            self.snapshot_sessions.append(session_id)
        return data

    def connect(self, session_id: str, player_id: str) -> _TestSocket:
        manager = self.client.websocket_connect(f"/api/ws/{session_id}?player_id={player_id}")
        return _TestSocket(manager.__enter__(), manager)


@pytest.fixture
def fake_model_server(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[tuple[TestClient, Path]]:
    log_dir = tmp_path / "logs"
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake")
    monkeypatch.setenv("LLM_MODEL", "fake/model")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_DIR", str(log_dir))
    monkeypatch.setattr(app_module, "DEFAULT_SAVES_DIR", tmp_path / "saves")
    monkeypatch.setattr(app_module, "LlmClient", FakeLlmClient)
    with TestClient(app_module.app) as client:
        yield client, log_dir


@pytest.mark.parametrize("raises_decision", [False, True])
def test_real_driver_completes_and_cleans_up_with_fake_model(
    fake_model_server: tuple[TestClient, Path],
    raises_decision: bool,
) -> None:
    client, log_dir = fake_model_server
    FakeLlmClient.raise_decision = raises_decision
    transport = ScenarioTestTransport(client)
    output: list[str] = []

    result = live_inner_self.run_scenario(transport, log_dir=log_dir, deadline_seconds=10, output=output.append)

    assert result.exit_code == 0
    assert result.completed is True
    assert transport.snapshot_sessions == [result.session_id, result.session_id, result.session_id]
    assert result.metrics["fallback_digests"] >= 1
    assert any("After combat" in line for line in output)
    assert any("After anchor leaves" in line for line in output)
    assert any(line == "WARN: LLM digest accepted" for line in output)
    with pytest.raises(ValueError, match="not found"):
        get_service().get_session(result.session_id)
    assert not list((log_dir.parent / "saves").rglob("*.json"))
