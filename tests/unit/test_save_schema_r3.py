"""Edge cases of the v1 → v2 save migration in storage.save_schema."""

from __future__ import annotations

from typing import Any

from dnd_simulator.storage.save_schema import SCHEMA_VERSION, migrate_v1_save


def _save(entities: object) -> dict[str, Any]:
    return {"schema_version": 1, "world": {"layers": {"entities": {"entities": entities}}}}


def _inner(result: object, entity_id: str = "n1") -> dict[str, Any]:
    assert isinstance(result, dict)
    inner = result["world"]["layers"]["entities"]["entities"][entity_id]["inner_self"]
    assert isinstance(inner, dict)
    return inner


class TestPassThrough:
    def test_non_dict_returned_unchanged(self) -> None:
        assert migrate_v1_save([1, 2]) == [1, 2]

    def test_other_version_returned_unchanged(self) -> None:
        data = {"schema_version": 2, "world": {}}
        assert migrate_v1_save(data) is data

    def test_missing_entities_path_bumps_nothing(self) -> None:
        data = {"schema_version": 1, "world": {"layers": {}}}
        result = migrate_v1_save(data)
        assert result == data
        assert result is not data

    def test_non_mapping_world_returned(self) -> None:
        data = {"schema_version": 1, "world": None}
        assert migrate_v1_save(data) == data

    def test_entities_not_a_dict_returned(self) -> None:
        data = _save(["n1"])
        result = migrate_v1_save(data)
        assert isinstance(result, dict)
        assert result["schema_version"] == 1

    def test_input_not_mutated(self) -> None:
        data = _save({"n1": {"entity_type": "npc", "memory": {"tags": ["angry"]}}})
        migrate_v1_save(data)
        assert "memory" in data["world"]["layers"]["entities"]["entities"]["n1"]


class TestEntityMigration:
    def test_non_npc_and_non_dict_entities_skipped(self) -> None:
        result = migrate_v1_save(_save({"p": {"entity_type": "player"}, "x": "junk"}))
        assert isinstance(result, dict)
        entities = result["world"]["layers"]["entities"]["entities"]
        assert "inner_self" not in entities["p"]
        assert entities["x"] == "junk"
        assert result["schema_version"] == SCHEMA_VERSION

    def test_non_dict_memory_becomes_empty_core(self) -> None:
        inner = _inner(migrate_v1_save(_save({"n1": {"entity_type": "npc", "memory": "broken"}})))
        assert inner["relations"] == []
        assert inner["mood"] == "neutral"
        assert inner["journal"] == ""

    def test_non_list_tags_ignored(self) -> None:
        inner = _inner(migrate_v1_save(_save({"n1": {"entity_type": "npc", "memory": {"tags": "angry"}}})))
        assert inner["mood"] == "neutral"

    def test_tags_mapped_with_duplicates_and_junk_dropped(self) -> None:
        tags = [7, "trusts:hero", "trusts:hero", "unknown:x", "loves:", "fleeing", "happy", "weird"]
        inner = _inner(migrate_v1_save(_save({"n1": {"entity_type": "npc", "memory": {"tags": tags}}})))
        assert inner["relations"] == [{"type": "trusts", "target_id": "hero"}]
        # "fleeing" → scared outranks happy
        assert inner["mood"] == "scared"

    def test_journal_and_conversation_carried(self) -> None:
        memory = {"recent": "Saw a dragon", "inner_state": "Afraid", "current_conversation": "hello"}
        inner = _inner(migrate_v1_save(_save({"n1": {"entity_type": "npc", "memory": memory}})))
        assert inner["journal"] == "Saw a dragon\n\nAfraid"
        assert inner["current_conversation"] == "hello"
        assert inner["goals"] == []
        assert inner["alignment"] == {"law_chaos": 0, "good_evil": 0}
