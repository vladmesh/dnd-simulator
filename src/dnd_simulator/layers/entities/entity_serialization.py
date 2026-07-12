"""Entity save serialization — the get_state half, split out of EntitiesLayer."""

from __future__ import annotations

from typing import cast

from dnd_simulator.core.character import Character, Creature, Entity
from dnd_simulator.core.class_features import FighterFeatures, PaladinFeatures, RogueFeatures
from dnd_simulator.core.container import Container
from dnd_simulator.core.intent import CreatureIntent, IntentType, TravelIntent
from dnd_simulator.core.items import Item
from dnd_simulator.core.models import EntityKind
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.entities.save_models import (
    AbilityScoresSave,
    AttackSave,
    ClassFeaturesSave,
    ContainerSave,
    CreatureSave,
    DamageComponentSave,
    EntitySave,
    ItemSave,
    LairOriginSave,
    NpcMemorySave,
    NpcSave,
    PlayerSave,
    ResourcePoolSave,
    TimedIntentSave,
    TravelIntentSave,
    TurnBudgetSave,
)


def serialize_entity(entity: Entity) -> dict[str, object]:
    """Serialize a single entity to a save dict."""
    save = entity_to_save_model(entity)
    return cast(dict[str, object], save.model_dump(mode="json", by_alias=True))


def player_to_save_data(player: PlayerCharacter) -> dict[str, object]:
    """Return the parse_player-compatible subset of PlayerSave."""
    save = _player_save(player)
    return cast(
        dict[str, object],
        save.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            include={
                "id",
                "name",
                "race",
                "class_",
                "level",
                "alignment",
                "appearance",
                "ability_scores",
                "hp",
                "ac",
                "gold",
                "speed",
                "start_location",
                "current_hp",
                "experience",
                "level_up_available",
                "items",
                "class_features",
                "combat_position",
                "reputation",
                "faction_id",
                "attacks",
            },
        ),
    )


def entity_to_save_model(entity: Entity) -> EntitySave:
    if isinstance(entity, PlayerCharacter):
        return _player_save(entity)
    if isinstance(entity, Npc):
        return _npc_save(entity)
    if isinstance(entity, Creature):
        return _creature_save(entity)
    if isinstance(entity, Container):
        return _container_save(entity)
    raise TypeError(f"Unsupported entity type for save: {type(entity).__name__}")


def _creature_save(entity: Creature) -> CreatureSave:
    return CreatureSave.model_validate({"entity_type": EntityKind.CREATURE, **_creature_fields(entity)})


def _player_save(player: PlayerCharacter) -> PlayerSave:
    items = _items_for_parse(player)
    return PlayerSave.model_validate(
        {
            "entity_type": EntityKind.PLAYER,
            **_creature_fields(player),
            "race": player.race,
            "class": player.char_class,
            "level": player.level,
            "alignment": player.alignment,
            "appearance": player.appearance,
            "hp": player.max_hp,
            "start_location": player.location_id,
            "experience": player.experience,
            "level_up_available": player.level_up_available,
            "items": items,
            "class_features": _class_features(player),
        }
    )


def _npc_save(npc: Npc) -> NpcSave:
    return NpcSave.model_validate(
        {
            "entity_type": EntityKind.NPC,
            **_creature_fields(npc),
            "race": npc.race,
            "class": npc.char_class,
            "level": npc.level,
            "role": npc.role,
            "personality": npc.personality,
            "description": npc.description,
            "settlement_id": npc.settlement_id,
            "location_override": npc.location_override,
            "memory": NpcMemorySave.model_validate(npc.memory.to_dict()),
            "ai_type": npc.ai_type,
            "hp": npc.max_hp,
            "ai": npc.ai_type,
            "start_location": npc.location_id,
            "items": _items_for_parse(npc),
            "class_features": _class_features(npc),
        }
    )


def _container_save(container: Container) -> ContainerSave:
    from dnd_simulator.content_loader.items import serialize_item

    return ContainerSave(
        entity_type=EntityKind.CONTAINER,
        id=container.id,
        name=container.name,
        location_id=container.location_id,
        active=container.active,
        temporary=container.temporary,
        faction_id=container.faction_id,
        is_open=container.is_open,
        gold=container.gold,
        inventory=[ItemSave.model_validate(serialize_item(item)) for item in container.inventory],
    )


def _creature_fields(entity: Creature) -> dict[str, object]:
    from dnd_simulator.content_loader.items import serialize_item

    data: dict[str, object] = {
        "id": entity.id,
        "name": entity.name,
        "location_id": entity.location_id,
        "active": entity.active,
        "temporary": entity.temporary,
        "faction_id": entity.faction_id,
        "max_hp": entity.max_hp,
        "current_hp": entity.current_hp,
        "ac": entity.ac,
        "speed": entity.speed,
        "ability_scores": AbilityScoresSave.model_validate(entity.ability_scores.to_dict()),
        "attacks": [
            AttackSave(
                name=attack.name,
                ability=attack.ability,
                damage=[DamageComponentSave(dice=damage.dice, type=damage.type) for damage in attack.damage],
                reach=attack.reach,
                is_finesse=attack.is_finesse,
            )
            for attack in entity.attacks
        ],
        "in_combat": entity.in_combat,
        "is_dodging": entity.is_dodging,
        "is_disengaging": entity.is_disengaging,
        "turn_budget": _turn_budget(entity),
        "conditions": dict(entity.conditions),
        "inventory": [ItemSave.model_validate(serialize_item(item)) for item in entity.inventory],
        "gold": entity.gold,
        "equipped_weapon": _item_save(entity.equipped_weapon),
        "equipped_armor": _item_save(entity.equipped_armor),
        "equipped_shield": _item_save(entity.equipped_shield),
        "equipped_head": _item_save(entity.equipped_head),
        "equipped_feet": _item_save(entity.equipped_feet),
        "equipped_ring": _item_save(entity.equipped_ring),
        "resource_pools": [
            ResourcePoolSave(
                id=pool.id,
                max_uses=pool.max_uses,
                current_uses=pool.current_uses,
                reset_on=pool.reset_on,
            )
            for pool in entity.resource_pools
        ],
        "reputation": dict(entity.reputation),
        "xp_value": entity.xp_value,
        "squad_id": entity.squad_id,
        "lair_origin": (
            LairOriginSave(
                lair_id=entity.lair_origin.lair_id,
                template_id=entity.lair_origin.template_id,
                role=entity.lair_origin.role,
            )
            if entity.lair_origin is not None
            else None
        ),
        "is_anchor": entity.is_anchor,
        "current_intent": _intent_save(entity.current_intent),
        "combat_position": entity.combat_position,
    }
    return data


def _intent_save(intent: CreatureIntent | None) -> TimedIntentSave | TravelIntentSave | None:
    if intent is None:
        return None
    if isinstance(intent, TravelIntent):
        return TravelIntentSave(
            kind=IntentType.TRAVEL,
            started_at_seconds=intent.started_at_seconds,
            destination_id=intent.destination_id,
            remaining_route=intent.remaining_route,
            next_arrival_seconds=intent.next_arrival_seconds,
        )
    return TimedIntentSave(
        kind=IntentType.WAIT if intent.kind is IntentType.WAIT else IntentType.SLEEP,
        started_at_seconds=intent.started_at_seconds,
        wake_at_seconds=intent.wake_at_seconds,
        rest_type=intent.rest_type,
    )


def _item_save(item: Item | None) -> ItemSave | None:
    if item is None:
        return None
    from dnd_simulator.content_loader.items import serialize_item

    return ItemSave.model_validate(serialize_item(item))


def _items_for_parse(entity: Creature) -> list[ItemSave]:
    from dnd_simulator.content_loader.items import EQUIPMENT_FIELDS, serialize_item

    items = [ItemSave.model_validate(serialize_item(item)) for item in entity.inventory]
    for field_name in EQUIPMENT_FIELDS:
        item = getattr(entity, field_name)
        if item is not None:
            item_data = serialize_item(item)
            item_data["equipped"] = True
            items.append(ItemSave.model_validate(item_data))
    return items


def _turn_budget(entity: Creature) -> TurnBudgetSave | None:
    if entity.turn_budget is None:
        return None
    return TurnBudgetSave(
        actions=entity.turn_budget.actions,
        bonus_actions=entity.turn_budget.bonus_actions,
        movement_remaining=entity.turn_budget.movement_remaining,
        reaction=entity.turn_budget.reaction,
    )


def _class_features(entity: Character) -> ClassFeaturesSave:
    data = ClassFeaturesSave()
    for feat in entity.class_features:
        if isinstance(feat, FighterFeatures):
            data.fighting_style = feat.fighting_style.value
        elif isinstance(feat, RogueFeatures):
            data.sneak_attack_dice = feat.sneak_attack_dice
        elif isinstance(feat, PaladinFeatures) and feat.fighting_style is not None:
            data.fighting_style = feat.fighting_style.value
    return data
