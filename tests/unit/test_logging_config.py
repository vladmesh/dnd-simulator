"""configure_logging keeps exception tracebacks in every sink."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog

from dnd_simulator.logging_config import configure_logging


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    config = structlog.get_config()
    yield
    structlog.reset_defaults()
    structlog.configure(**config)
    root.handlers[:] = handlers
    root.setLevel(level)


def _raise_boom() -> None:
    raise ValueError("boom")


def _log_exception() -> None:
    logger = structlog.get_logger(domain="session")
    try:
        _raise_boom()
    except ValueError:
        logger.exception("disconnect_stop_failed", session_id="s1")


def _assert_traceback(text: str) -> None:
    assert "Traceback (most recent call last)" in text
    assert "ValueError: boom" in text
    assert "in _raise_boom" in text


def _set_tty(monkeypatch: pytest.MonkeyPatch, tty: bool) -> None:
    monkeypatch.setattr(sys.stderr, "isatty", lambda: tty, raising=False)


def test_json_mode_record_carries_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_tty(monkeypatch, False)
    configure_logging(log_level=logging.INFO)

    _log_exception()

    record = json.loads(capsys.readouterr().out.strip())
    assert record["event"] == "disconnect_stop_failed"
    assert "exc_info" not in record
    _assert_traceback(record["exception"])


def test_console_mode_pretty_prints_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _set_tty(monkeypatch, True)
    configure_logging(log_level=logging.DEBUG)

    _log_exception()

    out = capsys.readouterr().out
    assert "disconnect_stop_failed" in out
    assert not out.lstrip().startswith("{")
    _assert_traceback(out)


@pytest.mark.parametrize("tty", [False, True], ids=["json", "console"])
def test_file_dispatch_record_carries_traceback(
    tty: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    _set_tty(monkeypatch, tty)
    configure_logging(log_level=logging.DEBUG, log_dir=tmp_path)

    _log_exception()

    lines = (tmp_path / "session_s1" / "full.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert "exc_info" not in record
    _assert_traceback(record["exception"])
    # The stderr sink still renders the exception after the file copy was written.
    _assert_traceback(capsys.readouterr().out)
