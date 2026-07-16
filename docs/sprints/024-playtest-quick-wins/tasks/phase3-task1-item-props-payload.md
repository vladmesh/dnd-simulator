# Task: Структурные свойства предметов в player-facing payload

**Date:** 2026-07-16
**Sprint:** 024-playtest-quick-wins
**Phase:** 3 — Панель свойств предметов

## Description

Игрок не видит, что делает предмет, до покупки/надевания (`item-properties-ui`, живая партия 2026-07-15). Сейчас единственный канал свойств — строка `describe_item()` (`core/awareness.py:65`): захардкоженный английский, без брони и щитов вовсе (для них возвращается голое `item.name`), уходит в native `title` tooltip. Типизированные дефы (`WeaponDef`/`ArmorDef`/`ShieldDef`/`AccessoryDef`, `core/items.py`) до фронта не доезжают.

Добавляем аддитивное поле `props` — JSON-safe словарь машиночитаемых значений, который фронт рендерит локализованными метками сам (клиентский i18n; серверный `ui-language-mixing` не трогаем):

```
weapon:    {kind: "weapon", damage: [{dice: "1d8", type: "slashing"}, ...], reach: 5,
            category: "simple"|"martial", ability: "dex"|null, modifier: 1, is_magic: bool,
            is_finesse/is_two_handed/is_light/is_heavy: bool, conditions: ["blessed", ...]}
armor:     {kind: "armor", category: "light"|"medium"|"heavy", base_ac: 18, max_dex_bonus: 0}
shield:    {kind: "shield", ac_bonus: 2}
accessory: {kind: "accessory", slot: "ring", modifiers: [{stat: "ac", op: "add", value: 1}]}
potion:    {kind: "potion", heal_dice: "2d4+2"}
```

Предмет без дефов и `heal_dice` → `props` отсутствует/`None`. Все значения — примитивы (enum'ы конвертируются в `.value` при сборке): payload'ы merchant-веток идут через `dataclasses.asdict` без сквозного `_json_safe`, Enum внутри dict-поля утёк бы в WS-сериализацию.

Точки прошивки:

- `core/awareness.py` — билдер `item_props(item: Item) -> dict[str, object] | None` рядом с `describe_item`; поля `props` на `ItemInfo` и `EquippedInfo` (default `None`).
- `layers/entities/awareness_builder.py` — `build_available_items` (:83), `build_merchants` (:126), `build_equipped` (:96), лутовая ветка (:312-351) заполняют `props`.
- `service/transport_payloads.py` — `build_inventory_payload` (:126) и `build_equipped_payload` (:117) кладут `props` в dict (они собирают словари руками, asdict их не спасает).

Границы: `describe_item` остаётся как есть — его едят LLM-промпты (`llm/brain.py:145,176` берут только `id`/`name`/`description`, так что `props` промпты не раздувает). Рендер на фронте — task 2.

## Tests First

Продуктовые сценарии на реальном резолве каталога (`parse_items([{"ref": ...}], catalog)`, паттерн из `TestSellStartingEquipmentFromCatalog`), не на hand-built `Item`:

- Игрок с `plate` в инвентаре → `build_inventory_payload` → запись несёт `props` с `kind="armor"`, `base_ac=18`, `max_dex_bonus=0`, `category="heavy"`.
- Торговец с `flaming_longsword` в продаже → peaceful awareness → `merchants[0].items[0].props`: две компоненты урона (`1d8 slashing` + `1d6 fire`), `modifier=1`, `is_magic=True`, `category="martial"`.
- `frost_dagger` → `props`: `is_finesse=True`, `is_light=True`, `ability="dex"`.
- Надетый `ring_of_protection` → `build_equipped_payload` → `props`: `kind="accessory"`, `slot="ring"`, `modifiers=[{stat:"ac", op:"add", value:1}]`.
- `health_potion` → `props`: `kind="potion"`, `heal_dice="2d4+2"`; `shield` → `ac_bonus=2`.
- JSON-safety: `json.dumps(props)` проходит для каждой записи каталога (параметризованный тест по всем 31 YAML — гарда от Enum-утечки и новых полей).

## Implementation

- `item_props()` — чистая функция-вьюха по образцу `describe_item`: ветки по `weapon_def`/`armor_def`/`shield_def`/`accessory_def`/`params["heal_dice"]`, enum'ы → `.value` на месте.
- `ItemInfo.props: dict[str, object] | None = None`, `EquippedInfo` аналогично — аддитивно, существующие конструкторы не ломаются.
- Merchant/available_items/loot ветки awareness едут через `dataclasses.asdict` — новое поле доезжает до WS само; руками прошивать только `build_inventory_payload`/`build_equipped_payload`.
- Тесты класть рядом с существующими: `test_inventory_awareness.py`, `test_srd_catalogs.py` (JSON-гарда), payload-тесты по образцу соседей `transport_payloads`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `props` доезжает по всем четырём каналам: инвентарь, экипировка, товары торговца, лут
- [ ] Все 31 записи каталога дают JSON-сериализуемый `props` (или его отсутствие для простых предметов)
- [ ] `describe_item`/LLM-промпты не тронуты

## Status

`pending`
