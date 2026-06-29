"""Worldbuilder lens: disk-based world/content editing off the GameService facade.

World templates, manifest inspection, layer-file read/write, and content/catalog CRUD.
All operations read or write YAML under ``content/`` — no live session state.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from dnd_simulator.content_loader import (
    LayerType,
    load_catalog,
    load_locations,
    load_nations,
    load_npcs,
    load_settlements,
    load_world,
    load_world_meta_from_manifest,
    resolve_manifest,
)
from dnd_simulator.content_loader.library import (
    TemplateInfo,
    list_compatible_templates,
    list_templates,
)
from dnd_simulator.rules.modifiers import effective_ac
from dnd_simulator.service.base import GameServiceProtocol

if TYPE_CHECKING:
    from dnd_simulator.content_loader.crud import EntityType as ContentEntityType


class WorldBuilderCommands(GameServiceProtocol):
    """Mixin: world templates, layer files, and content/catalog CRUD (worldbuilder lens)."""

    def list_worlds(self, lang: str = "en") -> list[dict[str, object]]:
        """List available world templates with completeness flag."""
        worlds_dir = self._content_dir / "worlds"
        result: list[dict[str, object]] = []
        if not worlds_dir.exists():
            return result
        for entry in sorted(worlds_dir.iterdir()):
            if entry.is_dir() and (entry / "manifest.yaml").exists():
                meta = load_world_meta_from_manifest(entry, lang=lang)
                resolved = resolve_manifest(entry, self._content_dir)
                complete = len(resolved) == len(LayerType)
                result.append({"id": entry.name, **meta, "complete": complete})
        return result

    def list_library_templates(self, layer_type: LayerType) -> list[TemplateInfo]:
        """List all library templates for a given layer type."""
        return list_templates(self._content_dir, layer_type)

    def list_compatible_library_templates(self, layer_type: LayerType, selected: dict[str, str]) -> list[TemplateInfo]:
        """List library templates compatible with already-selected layers."""
        return list_compatible_templates(self._content_dir, layer_type, selected)

    def get_world_template(self, world_id: str) -> dict[str, Any]:
        """Read a world template from disk (YAML data, not a live session)."""
        from dnd_simulator.content_loader import load_battle_maps

        self._validate_world_id(world_id)
        world_path = self._content_dir / "worlds" / world_id
        if not world_path.exists():
            raise FileNotFoundError(f"World '{world_id}' not found")

        layer_paths = resolve_manifest(world_path, self._content_dir)
        meta = load_world_meta_from_manifest(world_path)
        regions = load_world(layer_paths["geography"])
        nations = load_nations(layer_paths["politics"])
        settlements = load_settlements(layer_paths["settlements"])
        locations = load_locations(layer_paths["geography"], regions)
        from dnd_simulator.content_loader.schemas import ItemContent

        item_catalog_dir = self._content_dir / "catalogs" / "items"
        item_catalog = load_catalog(item_catalog_dir, ItemContent) if item_catalog_dir.exists() else {}
        npcs_list = load_npcs(
            layer_paths["entities"],
            known_locations={loc.id for loc in locations},
            item_catalog=item_catalog,
        )
        battle_maps = load_battle_maps(layer_paths["geography"])

        return {
            "id": world_id,
            "name": meta["name"],
            "description": meta.get("description", ""),
            "regions": [
                {
                    "id": r.id,
                    "name": r.name,
                    "terrain": r.terrain.value,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "elevation": r.elevation,
                    "water_proximity": r.water_proximity,
                    "connections": [{"target": c.target_id, "direction": c.direction.value} for c in r.connections],
                    "has_battle_map": r.id in battle_maps,
                }
                for r in regions
            ],
            "settlements": [
                {
                    "id": s.id,
                    "name": s.name,
                    "region_id": s.region_id,
                    "type": s.type.value,
                    "population": s.population,
                    "prosperity": s.prosperity,
                    "defenses": s.defenses,
                }
                for s in settlements
            ],
            "locations": [
                {
                    "id": loc.id,
                    "name": loc.name,
                    "region_id": loc.region_id,
                    "settlement_id": loc.settlement_id,
                    "description": loc.description,
                    "neighbors": [{"target": e.target_id, "distance": e.distance_m} for e in loc.edges],
                }
                for loc in locations
            ],
            "nations": [
                {
                    "id": n.id,
                    "name": n.name,
                    "regions": n.regions,
                    "wealth": n.wealth,
                    "military": n.military,
                    "stability": n.stability,
                    "leader": {"name": n.leader.name, "age": n.leader.age, "trait": n.leader.trait.value}
                    if n.leader
                    else None,
                }
                for n in nations
            ],
            "npcs": [
                {
                    "id": npc.id,
                    "name": npc.name,
                    "role": npc.role.value,
                    "location_id": npc.location_id,
                    "settlement_id": npc.settlement_id,
                    "personality": npc.personality,
                    "race": npc.race.value,
                    "char_class": npc.char_class.value,
                    "hp": npc.max_hp,
                    "ac": effective_ac(npc),
                    "ai_type": npc.ai_type,
                }
                for npc in npcs_list
            ],
        }

    def assemble_world(
        self,
        world_id: str,
        name: str,
        description: str,
        layer_selections: dict[str, str],
        default_player_faction: str,
        creator: str = "",
    ) -> dict[str, str]:
        """Assemble a new world from library templates.

        Creates a world directory with a manifest pointing to library templates.
        Returns ``{"id": ..., "name": ...}``.
        """
        from dnd_simulator.content_loader.assembly import assemble_world

        assemble_world(
            content_dir=self._content_dir,
            world_id=world_id,
            name=name,
            description=description,
            layer_selections=layer_selections,
            default_player_faction=default_player_faction,
            creator=creator,
        )
        return {"id": world_id, "name": name}

    def create_empty_world(
        self,
        world_id: str,
        name: str,
        description: str,
        default_player_faction: str,
        creator: str = "",
    ) -> dict[str, str]:
        """Create a new empty world (no layers defined).

        Returns ``{"id": ..., "name": ...}``.
        """
        from dnd_simulator.content_loader.assembly import create_empty_world

        create_empty_world(
            content_dir=self._content_dir,
            world_id=world_id,
            name=name,
            description=description,
            default_player_faction=default_player_faction,
            creator=creator,
        )
        return {"id": world_id, "name": name}

    _BASE_WORLDS: frozenset[str] = frozenset({"sword_vale", "test_vale"})

    @property
    def base_worlds(self) -> frozenset[str]:
        return self._BASE_WORLDS

    def fork_world(
        self,
        source_world_id: str,
        new_world_id: str,
        from_layer: str | None = None,
        creator: str = "",
    ) -> dict[str, object]:
        """Fork a world, optionally truncating layers from a given type upward.

        The new world is owned by the forking user (``creator``), not the source's creator.
        Returns world info dict with id, name, creator, complete.
        """
        from dnd_simulator.content_loader.assembly import fork_world

        layer_type = LayerType(from_layer) if from_layer else None
        fork_world(
            content_dir=self._content_dir,
            source_world_id=source_world_id,
            new_world_id=new_world_id,
            from_layer=layer_type,
            creator=creator,
        )
        new_world_path = self._content_dir / "worlds" / new_world_id
        meta = load_world_meta_from_manifest(new_world_path)
        resolved = resolve_manifest(new_world_path, self._content_dir)
        complete = len(resolved) == len(LayerType)
        return {"id": new_world_id, "name": meta["name"], "creator": meta["creator"], "complete": complete}

    def delete_world(self, world_id: str) -> None:
        """Delete a world. Blocked for base worlds and worlds with active sessions."""
        from dnd_simulator.content_loader.assembly import delete_world

        self._validate_world_id(world_id)
        if world_id in self._BASE_WORLDS:
            raise ValueError(f"Cannot delete base world '{world_id}'")

        for session in self._sessions.values():
            if session.world_name == world_id:
                raise RuntimeError(f"Cannot delete world '{world_id}' — active session exists")

        delete_world(self._content_dir, world_id)

    def get_world_manifest(self, world_id: str, lang: str = "en") -> dict[str, object]:
        """Read manifest.yaml and return structured layer info for the world inspector."""
        from dnd_simulator.content_loader.manifest import LayerSource
        from dnd_simulator.content_loader.utils import _read_yaml, resolve_text

        self._validate_world_id(world_id)
        world_path = self._content_dir / "worlds" / world_id
        if not world_path.exists():
            raise FileNotFoundError(f"World '{world_id}' not found")

        manifest = _read_yaml(world_path / "manifest.yaml")
        name = resolve_text(manifest["name"], lang)
        layers_data = manifest["layers"]
        layers: list[dict[str, str | None]] = []
        for layer_type in LayerType:
            lt = layer_type.value
            layer_config = layers_data.get(lt)
            if layer_config is None:
                layers.append({"layer_type": lt, "source": None, "template": None, "version": None})
            else:
                source = LayerSource(layer_config["source"])
                layers.append(
                    {
                        "layer_type": lt,
                        "source": source.value,
                        "template": str(layer_config["template"]) if source == LayerSource.LIBRARY else None,
                        "version": str(layer_config["version"]) if source == LayerSource.LIBRARY else None,
                    }
                )
        return {"world_id": world_id, "name": name, "layers": layers}

    def scaffold_layer(self, world_id: str, layer_type: LayerType) -> Path:
        """Create a minimal valid custom layer from scratch."""
        from dnd_simulator.content_loader.assembly import scaffold_layer

        self._validate_world_id(world_id)
        return scaffold_layer(self._content_dir, world_id, layer_type)

    def fork_layer(self, world_id: str, layer_type: LayerType) -> Path:
        """Fork a library template into a world's custom directory."""
        from dnd_simulator.content_loader.assembly import fork_layer

        self._validate_world_id(world_id)
        return fork_layer(self._content_dir, world_id, layer_type)

    # -- Layer files (read/write YAML) --

    def _resolve_layer_path(self, world_id: str, layer_type: LayerType) -> tuple[Path, str]:
        """Resolve the directory for a layer and return (path, source)."""
        from dnd_simulator.content_loader.manifest import LayerSource
        from dnd_simulator.content_loader.utils import _read_yaml

        self._validate_world_id(world_id)
        world_path = self._content_dir / "worlds" / world_id
        if not world_path.is_dir():
            raise FileNotFoundError(f"World '{world_id}' not found")

        manifest = _read_yaml(world_path / "manifest.yaml")
        layer_config = manifest["layers"][layer_type.value]
        source = LayerSource(layer_config["source"])

        layer_paths = resolve_manifest(world_path, self._content_dir)
        return layer_paths[layer_type.value], source.value

    _SAFE_ID_RE = __import__("re").compile(r"^[a-z0-9][a-z0-9_-]*$")

    @classmethod
    def _validate_world_id(cls, world_id: str) -> None:
        """Reject path-traversal attempts in world_id."""
        if not cls._SAFE_ID_RE.match(world_id):
            raise ValueError(f"Invalid world_id: {world_id!r}")

    @staticmethod
    def _validate_filename(filename: str) -> None:
        """Validate filename is a safe, bare .yaml name."""
        if (
            "/" in filename
            or "\\" in filename
            or ".." in filename
            or filename.startswith(".")
            or not filename.endswith(".yaml")
        ):
            raise ValueError(f"Invalid filename: {filename!r}")

    def get_layer_files(self, world_id: str, layer_type: LayerType) -> dict[str, str]:
        """List all data YAML files in a layer directory with their contents.

        Excludes metadata.yaml (library bookkeeping). Works for both library and custom layers.
        """
        layer_path, _source = self._resolve_layer_path(world_id, layer_type)

        result: dict[str, str] = {}
        for f in sorted(layer_path.iterdir()):
            if f.is_file() and f.suffix == ".yaml" and f.name != "metadata.yaml":
                result[f.name] = f.read_text(encoding="utf-8")
        return result

    def get_layer_file(self, world_id: str, layer_type: LayerType, filename: str) -> str:
        """Read a single YAML file from a layer directory."""
        self._validate_filename(filename)
        layer_path, _source = self._resolve_layer_path(world_id, layer_type)

        file_path = layer_path / filename
        if not file_path.is_file():
            raise FileNotFoundError(f"File '{filename}' not found in {layer_type.value} layer")
        return file_path.read_text(encoding="utf-8")

    def update_layer_file(self, world_id: str, layer_type: LayerType, filename: str, content: str) -> None:
        """Write content to a YAML file in a custom layer.

        Rejects writes to library layers, invalid filenames, and invalid YAML.
        """
        import yaml

        self._validate_filename(filename)
        layer_path, source = self._resolve_layer_path(world_id, layer_type)

        if source == "library":
            raise ValueError(f"Cannot write to library layer '{layer_type.value}' — fork it first")

        try:
            yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError(f"Invalid YAML: {exc}") from exc

        (layer_path / filename).write_text(content, encoding="utf-8")

    # -- Content entity CRUD --

    def _resolve_entity_layer_path(
        self,
        world_id: str,
        entity_type: ContentEntityType,
    ) -> tuple[Path, str]:
        """Resolve the layer directory for a content entity type. Returns (path, source)."""
        from dnd_simulator.content_loader.crud import get_registry_entry

        entry = get_registry_entry(entity_type)
        assert entry.layer_type is not None
        return self._resolve_layer_path(world_id, LayerType(entry.layer_type))

    def list_content_entities(
        self,
        world_id: str,
        entity_type: ContentEntityType,
    ) -> list[dict[str, object]]:
        """List all entities of a type from a world layer."""
        from dnd_simulator.content_loader.crud import list_entities

        layer_path, _source = self._resolve_entity_layer_path(world_id, entity_type)
        entities = list_entities(entity_type, layer_path)
        return [{"id": eid, "data": model.model_dump(mode="json", by_alias=True)} for eid, model in entities.items()]

    def get_content_entity(
        self,
        world_id: str,
        entity_type: ContentEntityType,
        entity_id: str,
    ) -> dict[str, object]:
        """Get a single entity from a world layer."""
        from dnd_simulator.content_loader.crud import get_entity

        layer_path, _source = self._resolve_entity_layer_path(world_id, entity_type)
        model = get_entity(entity_type, entity_id, layer_path)
        return {"id": entity_id, "data": model.model_dump(mode="json", by_alias=True)}

    def create_content_entity(
        self,
        world_id: str,
        entity_type: ContentEntityType,
        entity_id: str,
        data: dict[str, object],
    ) -> dict[str, object]:
        """Create an entity in a custom world layer. Rejects writes to library layers."""
        from dnd_simulator.content_loader.crud import create_entity

        layer_path, source = self._resolve_entity_layer_path(world_id, entity_type)
        if source == "library":
            raise ValueError("Cannot write to library layer — fork it first")
        model = create_entity(entity_type, entity_id, data, layer_path)
        return {"id": entity_id, "data": model.model_dump(mode="json", by_alias=True)}

    def update_content_entity(
        self,
        world_id: str,
        entity_type: ContentEntityType,
        entity_id: str,
        data: dict[str, object],
    ) -> dict[str, object]:
        """Update an entity in a custom world layer. Rejects writes to library layers."""
        from dnd_simulator.content_loader.crud import update_entity

        layer_path, source = self._resolve_entity_layer_path(world_id, entity_type)
        if source == "library":
            raise ValueError("Cannot write to library layer — fork it first")
        model = update_entity(entity_type, entity_id, data, layer_path)
        return {"id": entity_id, "data": model.model_dump(mode="json", by_alias=True)}

    def delete_content_entity(
        self,
        world_id: str,
        entity_type: ContentEntityType,
        entity_id: str,
    ) -> None:
        """Delete an entity from a custom world layer. Rejects writes to library layers."""
        from dnd_simulator.content_loader.crud import delete_entity

        layer_path, source = self._resolve_entity_layer_path(world_id, entity_type)
        if source == "library":
            raise ValueError("Cannot write to library layer — fork it first")
        delete_entity(entity_type, entity_id, layer_path)

    # -- Catalog CRUD --

    def list_catalog_entries(
        self,
        entity_type: ContentEntityType,
    ) -> list[dict[str, object]]:
        """List all catalog entries of a type."""
        from dnd_simulator.content_loader.crud import list_catalog_entries

        entries = list_catalog_entries(entity_type, self._content_dir)
        return [{"id": eid, "data": model.model_dump(mode="json", by_alias=True)} for eid, model in entries.items()]

    def get_catalog_entry(
        self,
        entity_type: ContentEntityType,
        entry_id: str,
    ) -> dict[str, object]:
        """Get a single catalog entry."""
        from dnd_simulator.content_loader.crud import get_catalog_entry

        model = get_catalog_entry(entity_type, entry_id, self._content_dir)
        return {"id": entry_id, "data": model.model_dump(mode="json", by_alias=True)}

    def create_catalog_entry(
        self,
        entity_type: ContentEntityType,
        entry_id: str,
        data: dict[str, object],
    ) -> dict[str, object]:
        """Create a catalog entry."""
        from dnd_simulator.content_loader.crud import create_catalog_entry

        model = create_catalog_entry(entity_type, entry_id, data, self._content_dir)
        return {"id": entry_id, "data": model.model_dump(mode="json", by_alias=True)}

    def update_catalog_entry(
        self,
        entity_type: ContentEntityType,
        entry_id: str,
        data: dict[str, object],
    ) -> dict[str, object]:
        """Update a catalog entry."""
        from dnd_simulator.content_loader.crud import update_catalog_entry

        model = update_catalog_entry(entity_type, entry_id, data, self._content_dir)
        return {"id": entry_id, "data": model.model_dump(mode="json", by_alias=True)}

    def delete_catalog_entry(
        self,
        entity_type: ContentEntityType,
        entry_id: str,
    ) -> None:
        """Delete a catalog entry."""
        from dnd_simulator.content_loader.crud import delete_catalog_entry

        delete_catalog_entry(entity_type, entry_id, self._content_dir)

    # -- Cross-layer refs --

    def list_refs(
        self,
        world_id: str,
        ref_type: str,
    ) -> list[dict[str, str]]:
        """Return ID+name pairs for cross-layer reference dropdowns.

        ref_type: locations, regions, settlements, nations, factions.
        """
        from dnd_simulator.content_loader.refs import RefType, get_ref_entries

        self._validate_world_id(world_id)
        rt = RefType(ref_type)  # raises ValueError on unknown
        return get_ref_entries(rt, world_id, self._content_dir)
