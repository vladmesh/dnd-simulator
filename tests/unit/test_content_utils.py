"""Direct tests for content_loader/utils.py — localizable text and YAML helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.content_loader.creatures import load_npcs, parse_class_features
from dnd_simulator.content_loader.library import _read_template_info
from dnd_simulator.content_loader.utils import (
    _load_section,
    _read_yaml,
    _write_yaml,
    as_int,
    as_list,
    as_mapping,
    as_mapping_list,
    resolve_text,
)
from dnd_simulator.core.character import CharClass


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

    def test_non_mapping_top_level_is_rejected(self, tmp_path: Path) -> None:
        path = tmp_path / "list.yaml"
        path.write_text("- a\n- b\n")
        with pytest.raises(ValueError, match="expected a mapping, got list"):
            _read_yaml(path)


class TestNarrowing:
    def test_as_mapping_stringifies_keys(self) -> None:
        assert as_mapping({1: "a", "b": 2}, "here") == {"1": "a", "b": 2}

    @pytest.mark.parametrize("value", [None, "text", [1], 3])
    def test_as_mapping_rejects_non_mappings(self, value: object) -> None:
        with pytest.raises(ValueError, match=r"^here: expected a mapping"):
            as_mapping(value, "here")

    def test_as_list_rejects_scalars(self) -> None:
        assert as_list([1, "a"], "here") == [1, "a"]
        with pytest.raises(ValueError, match=r"^here: expected a list, got str"):
            as_list("medieval", "here")

    def test_as_mapping_list_names_the_bad_index(self) -> None:
        assert as_mapping_list([{"a": 1}], "items") == [{"a": 1}]
        with pytest.raises(ValueError, match=r"^items\[1\]: expected a mapping"):
            as_mapping_list([{"a": 1}, "oops"], "items")

    @pytest.mark.parametrize(("value", "expected"), [(3, 3), ("4", 4), (2.0, 2), (True, 1)])
    def test_as_int_converts_scalars_like_int(self, value: object, expected: int) -> None:
        assert as_int(value, "here") == expected

    @pytest.mark.parametrize("value", [None, [1], {"a": 1}])
    def test_as_int_rejects_non_scalars(self, value: object) -> None:
        with pytest.raises(ValueError, match=r"^here: expected an integer"):
            as_int(value, "here")


class TestBadContentIsNamed:
    def test_library_tags_must_be_a_list(self, tmp_path: Path) -> None:
        _write_yaml(
            tmp_path / "metadata.yaml",
            {"name": "T", "layer_type": "geography", "version": "1", "tags": "medieval"},
        )
        with pytest.raises(ValueError, match="tags: expected a list, got str"):
            _read_template_info(tmp_path, "t")

    def test_npc_entry_must_be_a_mapping(self, tmp_path: Path) -> None:
        _write_yaml(tmp_path / "npcs.yaml", {"guard": "oops"})
        with pytest.raises(ValueError, match=r"npcs\.guard: expected a mapping, got str"):
            load_npcs(tmp_path)

    def test_class_features_block_must_be_a_mapping(self) -> None:
        with pytest.raises(ValueError, match="class_features: expected a mapping, got str"):
            parse_class_features(CharClass.FIGHTER, {"class_features": "defense"})
