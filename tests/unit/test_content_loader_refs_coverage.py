"""Coverage for reference names that are absent or unset."""

from types import SimpleNamespace

import pytest

from dnd_simulator.content_loader.refs import _resolve_name


@pytest.mark.parametrize("model", [object(), SimpleNamespace(name=None)], ids=["missing-name", "unset-name"])
def test_resolve_name_returns_empty_string_without_a_name(model: object) -> None:
    assert _resolve_name(model, "en") == ""
