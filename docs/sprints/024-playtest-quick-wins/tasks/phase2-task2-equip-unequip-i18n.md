# Task: i18n кнопок надеть/снять

**Date:** 2026-07-16
**Sprint:** 024-playtest-quick-wins
**Phase:** 2 — Полировка торговли и экипировки

## Description

Кнопки экипировки в боевом action bar и в инвентаре показывают сырые ID и английские тексты под RU (`action-bar-equip-i18n`, `action-bar-unequip-i18n`, живая партия 2026-07-15 + E2E sprint 020). Оба айтема — одна семья по 12 экипировочным `ActionType`; бэклог требует чинить их одним PR. Делается сейчас вместе, коллапс 12 ActionType в один (`equip-action-collapse`) отложен и этот таск его не трогает.

Два независимых слоя текста:

**Метки (frontend).** `getActionLabel` (`frontend/src/components/game/action-bar/utils.ts:9-13`) ищет ключ `game:<name>` в i18next, иначе возвращает сырой snake_case ID. В `en/game.json`/`ru/game.json` есть только `equip`/`unequip` (строки 89-90); нет ключей `equip_armor`, `equip_shield`, `equip_head`, `equip_feet`, `equip_ring` и их `unequip_*` — они рендерятся как «equip_armor». Плюс в `InventoryPanel.tsx` кнопки в сумке хардкодят английские литералы `"USE"` (строка 102) и `"EQUIP"` (строка 111) мимо i18n.

**Описания (backend).** Описания `ActionDef` приходят по проводу уже переведёнными: `transport_payloads.py:52` делает `_(definition.description)`, фронт рендерит строку как есть (`InventoryDrawer.tsx:52`, `ActionButton` `title`). Msgid'ы equip/unequip описаний помечены `N_()` в `_EQUIP_ACTION_SPECS` (`core/action_defs.py:336-413`) и извлечены в `.pot`, но в RU-каталоге `locale/ru/LC_MESSAGES/dnd_simulator.po` их переводов нет — под RU описания текут по-английски («Put away your equipped weapon. You will fight with fists.», «Remove your equipped armor.» и т.д.). Решение по бэклогу: переводить в `.po` (не переключать описания на фронтовые ключи).

Фикс: добавить 10 недостающих slot-меток в `en`/`ru` `game.json`, увести хардкод `USE`/`EQUIP` из `InventoryPanel.tsx` в `t()`, и добавить RU-переводы 12 описаний equip/unequip (6 equip + 6 unequip) в `.po` с перекомпиляцией `.mo`.

## Tests First

Продуктовые сценарии (русский игрок видит русские кнопки и подсказки, не сырые ID и не английский):

- **Backend:** транспортный payload доступных действий, собранный под `DND_LANGUAGE=ru`, отдаёт `description` для `equip_armor`, `unequip_armor`, `unequip_shield` и `unequip` (оружие) на русском, не английскую строку. Прогоняет `_(definition.description)` + `.po`. Собрать через существующий билдер payload'а действий (`transport_payloads`) на реальном `action_defs`.
- **Frontend:** под i18n `lng=ru` метки всех 10 slot-действий (`equip_armor`/`unequip_armor`/`equip_shield`/`unequip_shield`/`equip_head`/`unequip_head`/`equip_feet`/`unequip_feet`/`equip_ring`/`unequip_ring`) резолвятся в непустой перевод, а не в сырой ID (`getActionLabel` не возвращает входное имя). Рендер `InventoryDrawer` с этими действиями не показывает snake_case строк.
- **Frontend:** в `InventoryPanel` кнопки экипировки/использования из сумки рендерят переведённый текст (ключ `game:*`), а не литералы `EQUIP`/`USE`.

## Implementation

- `frontend/src/i18n/locales/en/game.json` и `ru/game.json` — добавить ключи `equip_armor`, `equip_shield`, `equip_head`, `equip_feet`, `equip_ring`, `unequip_armor`, `unequip_shield`, `unequip_head`, `unequip_feet`, `unequip_ring` (EN — человекочитаемые «Equip Armor»/«Remove Armor», RU — «Надеть броню»/«Снять броню» и т.д. в тоне соседних `equip`/`unequip`/`slot_*`).
- `frontend/src/components/game/InventoryPanel.tsx` — заменить литералы `"USE"` (строка 102) и `"EQUIP"` (строка 111) на `t("game:use_item")`/`t("game:equip")` (или новые короткие ключи), добавить недостающие ключи в оба `game.json`.
- Backend `.po`: `make messages` для актуализации `.pot`, влить новые msgid'ы в `locale/ru/LC_MESSAGES/dnd_simulator.po` (msgmerge при необходимости), перевести 12 описаний из `_EQUIP_ACTION_SPECS` (weapon equip/unequip, armor, shield, head, feet, ring), `make compile-messages` для `.mo`. EN base не трогаем.
- Строки короткие, без em-dash; тон — как у существующих боевых меток и `equip`/`unequip`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] 10 slot-меток есть в `en` и `ru` `game.json`; slot-действия не показывают сырой ID
- [ ] `USE`/`EQUIP` в `InventoryPanel` идут через `t()`, не хардкод
- [ ] 12 описаний equip/unequip переведены в RU `.po`, `.mo` перекомпилированы; под RU описания русские
- [ ] Веб-действия (wire-контракт 12 `ActionType`) не изменены — коллапс вне скоупа

## Status

`pending`
