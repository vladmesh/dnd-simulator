# Task: SRD-цены для каталога предметов

**Date:** 2026-07-16
**Sprint:** 024-playtest-quick-wins
**Phase:** 2 — Полировка торговли и экипировки

## Description

Стартовое снаряжение нельзя продать торговцу (`catalog-item-prices`, живая партия 2026-07-15). `validate_sell` (`rules/trade.py:46-47`) и `validate_buy` (`rules/trade.py:30-31`) отбивают сделку при `item.price is None` строкой «Item has no price and cannot be traded». Ни одна запись в `content/catalogs/items/` не задаёт `price`, а схема дефолтит его в `None` (`content_loader/schemas.py:129`), поэтому всё, что резолвится из каталога (стартовое, лутовое, купленное), приходит с `price=None` и не торгуется.

Плумбинг цены полностью на месте: `resolve_item_ref` (`content_loader/items.py:164-186`) мёржит поля каталога, `_to_item` ставит `Item.price=model.price` (`items.py:155`), сериализация round-trip'ит цену. Не хватает только данных — значений `price` в YAML.

Фикс: проставить SRD-цены (PHB) в 31 каталожный YAML. Для мандановых предметов — таблица PHB (в золотых). Для магических (`flaming_longsword`, `frost_dagger`, `ring_of_protection`, `boots_of_speed`, `circlet_of_aim`) цены в SRD нет — задать разумные значения по редкости (источник — DMG/домашние; uncommon ≈ 200–500, rare ≈ 2000–5000 gp).

Границы: не трогаем механику скидки при продаже — сейчас buy и sell идут по одной `item.price` (наценки нет), это существующее поведение и вне скоупа. Экипированный предмет продать нельзя (лежит в `Creature.equipped`, а не в `inventory`; `_find_item` смотрит только `inventory`) — это тоже существующее поведение, отдельной ошибки не добавляем; сценарий продажи снятого предмета работает и его надо покрыть тестом.

Ориентир по мандановым (PHB, gp): dagger 2, longsword 15, rapier 25, greataxe 30, greatsword 50, mace 5, quarterstaff 1, shortsword 10, warhammer 15, shortbow 25, longbow 50, hand_crossbow 75; padded 5, leather 10, hide 10, studded_leather 45, ring_mail 30, chain_shirt 50, scale_mail 50, chain_mail 75, splint 200, breastplate 400, half_plate 750, plate 1500, shield 10; health_potion 50.

## Tests First

Продуктовые сценарии (реальная цепочка каталог → резолв → правила торговли):

- Игрок со снятым стартовым предметом, резолвнутым из каталога через `ref:` (напр. `chain_mail`), лежащим в инвентаре, на локации торговца → действие `sell` → золото игрока выросло на `price`, предмет ушёл из инвентаря, ошибки нет. Это прогоняет `resolve_item_ref` → `Item.price` → `validate_sell` → `execute_sell` → `transfer_items`.
- Регресс-гварда каталога: каждая запись `content/catalogs/items/*.yaml` после парсинга через `parse_items`/каталог-лоадер несёт `price is not None` (параметризованный тест по всем файлам), чтобы будущая запись без цены падала в тесте, а не в живой партии.
- `validate_sell`/`validate_buy` для предмета с `price=None` по-прежнему отбивают со старой ошибкой (гварду не ломаем — существующий `test_rejects_unpriceable_item` расширить на sell).

## Implementation

- `content/catalogs/items/*.yaml` — добавить `price: <int>` в каждую из 31 записи по таблице выше; магические — по редкости.
- Проверить, что новых полей схема не отвергает: `ItemContent` — `extra="forbid"`, но `price` уже объявлен, так что YAML принимается без правок схемы.
- Тест продажи собрать на реальном резолве каталога (не `Item(price=...)` вручную), чтобы поймать разрыв данные↔правила.
- Правок Python-кода торговли не требуется; если тест продажи проще собрать через хендлер `handle_sell`/WS — переиспользовать существующие фикстуры из `test_trade_handlers.py`/`test_trade_ws.py`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Все 31 записи каталога несут `price`
- [ ] Снятый стартовый предмет продаётся торговцу из инвентаря (золото растёт, предмет уходит)
- [ ] Гварда `price is None` не сломана (priceless по-прежнему отбивается)

## Status

`done`

## Developer Notes

Плумбинг цены уже был на месте — правок Python не потребовалось. Добавлен `price:` в 31 каталожный YAML: манданое — по таблице PHB (dagger 2 … plate 1500, shield 10, health_potion 50; quarterstaff округлён 2sp→1gp), магическое (`flaming_longsword`/`frost_dagger`/`circlet_of_aim` 2500, `ring_of_protection` 3500, `boots_of_speed` 4000) — по редкости DMG, домашние значения.

Тесты: `TestCatalogPrices` в `test_srd_catalogs.py` (every entry has price / prices positive / price survives ref-resolve в runtime Item) как регресс-гварда против забытого `price:`; `TestSellStartingEquipmentFromCatalog` в `test_trade.py` продаёт `chain_mail`, резолвнутый через `parse_items([{"ref": "chain_mail"}], catalog)` (не hand-built `Item`), проверяя цепочку каталог→resolve→validate_sell→execute_sell→transfer_items и рост золота на `price`; `test_sell_rejects_unpriceable_item` расширил гварду `price is None` на sell.

Проверка `execute_sell` во время разведки: `gold=-price` корректен (src/dst меняются местами между buy и sell, `transfer_items` делает `src.gold -= gold; dst.gold += gold`), продавец получает золото — флаг ревью-агента был ложным.

`make check` зелёный (backend 2563 = 2558 + 5 новых, frontend 289). Наценки при продаже нет (buy и sell по одной `item.price`) — существующее поведение, вне скоупа. Экипированный предмет по-прежнему не продаётся (лежит в `equipped`, не в `inventory`) — тоже вне скоупа, покрыт сценарий продажи снятого.
