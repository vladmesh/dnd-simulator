"""Direct tests for content_loader/utils.py — localizable text and YAML helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.content_loader.utils import _load_section, _read_yaml, _write_yaml, resolve_text


class TestResolveText:
    def test_plain_string_is_returned_as_is(self) -> None:
        assert resolve_text("Sword Vale", lang="ru") == "Sword Vale"

    def test_picks_the_requested_language(self) -> None:
        assert resolve_text({"en": "Sword Vale", "ru": "Долина Мечей"}, lang="ru") == "Долина Мечей"

    def test_falls_back_to_english(self) -> None:
        assert resolve_text({"en": "Sword Vale", "de": "Schwerttal"}, lang="ru") == "Sword Vale"

    def test_falls_back_to_first_available_without_english(self) -> None:
        assert resolve_text({"de": "Schwerttal", "fr": "Val des Épées"}, lang="ru") == "Schwerttal"

    def test_empty_translation_falls_through(self) -> None:
        assert resolve_text({"en": "Sword Vale", "ru": ""}, lang="ru") == "Sword Vale"

    def test_empty_mapping_gives_empty_string(self) -> None:
        assert resolve_text({}, lang="en") == ""

    @pytest.mark.parametrize(("value", "expected"), [(42, "42"), (None, "None")])
    def test_non_text_values_are_stringified(self, value: object, expected: str) -> None:
        assert resolve_text(value) == expected


class TestYamlHelpers:
    def test_missing_file_reads_as_empty(self, tmp_path: Path) -> None:
        assert _read_yaml(tmp_path / "absent.yaml") == {}

    def test_empty_file_reads_as_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("")
        assert _read_yaml(path) == {}

    def test_write_keeps_unicode_and_key_order(self, tmp_path: Path) -> None:
        path = tmp_path / "out.yaml"
        data: dict[str, object] = {"zeta": {"ru": "Долина"}, "alpha": [1, 2]}

        _write_yaml(path, data)

        text = path.read_text()
        assert "Долина" in text
        assert text.index("zeta") < text.index("alpha")
        assert _read_yaml(path) == data

    def test_load_section_reads_the_section_file(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "regions.yaml", {"north": {"name": "North"}})
        assert _load_section(tmp_path, "regions") == {"north": {"name": "North"}}
        assert _load_section(tmp_path, "nations") == {}
