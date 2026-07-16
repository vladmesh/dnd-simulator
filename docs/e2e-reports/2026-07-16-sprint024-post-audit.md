# E2E Report: sprint024-post-audit

**Date:** 2026-07-16
**Flags:** --no-llm
**Sections tested:** 1, 2, 3, 5, 6 (частично), 8, 9, 10, 11.1, 13.2/13.3, 15.1/15.5, 16.1/16.2 + авто-сценарии по аудит-фиксам
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, мир Sword Vale, RU UI

Пост-аудитный прогон спринта 024. С момента phase3-E2E изменились только два аудит-квикфикса
(`reaction_to_dict` в public API transport_payloads, снос обёртки `check_faction_hostility` в awareness_builder),
поэтому фокус — реакции/OA, hostility в perception и общий смоук.

## Summary

- Scenarios: 26 tested, 26 passed (0 failed)
- Quick fixes: 0
- Blockers: 0

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing Player/DM split | pass | |
| 1.2 | Quick start Sword Vale | pass | Сессия, WS, первый ход |
| 1.3 | Language toggle EN→RU | pass | Все лейблы переключаются |
| 1.4 | Point buy | pass | 15/27→3/27, + disabled на 15, HP 12, AC 19 c Defense |
| 1.5 | Class-specific UI | pass | Rogue: селектор стиля исчезает, экипировка меняется, HP 10 / AC 11 |

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.1 | Perception nearby | pass | marta с кнопками Атаковать/Говорить/Осмотреть |
| 2.2 | Talk to NPC | pass | Canned-ответ «Что будете заказывать?»; в логе NPC назван «человек», в панели — marta |
| 2.3 | Wait +1 час | pass | 10:00→11:00 ровно, без потока NPC-ходов (16.1) |
| 2.4 | Move between locations | pass | Таверна→рынок→ворота, панели обновляются (16.2 short-edge) |

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | Атака gretta → авто-бой, инициатива в логе, sidebar → CombatPanel (13.3) |
| 3.2 | Attack and damage | pass | Полный breakdown `[d20(7)+5=12 vs КЗ 10], 5 урона (1d8 рубящий + 1d6 огненный + +2 str)` |
| 3.3 | End turn / NPC response | pass | gretta экипирует Кинжал (лог локализован), атакует |
| 3.4 | Combat ends | pass | «человек погибает», репутация 100→80 (13.2), «Бой окончен», layout возвращается |

### Section 5 + 8: Equipment & Accessories

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 5.1 | Equip weapon | pass | Flaming Longsword из сумки, слот обновился, атака новым оружием |
| 5.3 | Use potion | pass* | Зелье потрачено; на полном HP лог «восстановлено 0 HP» — см. Findings |
| 8.1 | Inventory panel | pass | 6 слотов + сумка + золото |
| 8.2 | Equip accessory | pass | Ring of Protection: AC 19→20 |
| 8.3 | Unequip accessory | pass | AC 20→19, слот пуст, предмет в сумке (ring не задет багом `ac-stale-on-unequip`) |
| 4.1 | Second Wind | pass | 3→8 HP (1d10+1), RU-сообщение, ненулевой путь фазы 1 цел |

### Section 9: Trading

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 9.1 | Open trade | pass | TradePanel с ценами, золото торговца видно |
| 9.2 | Buy item | pass | Potion 50g: 1000→950, у торговца 500→550, предмет ушёл из витрины |
| 9.3 | Sell item | pass | Продажа зелья 450→500, предмет вернулся к торговцу |
| 9.4 | Insufficient gold | pass | Кнопки «Купить» (600g/550g при 450g) disabled — покупка невозможна на уровне UI |

### Section 10-11: Layout & Reactions

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.1 | Three-column dashboard | pass | |
| 10.2 | Log expand overlay | pass | Оверлей корректно перехватывает клики, закрытие работает |
| 10.3 | NPC inspect modal | pass | «Ser Aldric», Человек · Стражник, фракция, описание из YAML |
| 10.4 | Click-to-move | pass | 25 ft списано атомарно: Движение 30→5фт (фаза 1 unified budget) |
| 10.5 | Combat layout switch | pass | BattleMap справа, CombatPanel слева, после боя возврат |
| 10.6 | Action bar budget | pass | Действия/Бонус/Движение/Реакция; после атаки Действия: 0, кнопки скрыты |
| 11.1 | OA on leaving reach | pass | «(атака возможности)» + «человек пользуется твоей оплошностью!», полностью RU |
| — | Flee (Бегство) | pass | «Ты пытаешься сбежать», бой завершён |

### Section 15: Loot

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 15.1 | Take all | pass | 1000g + 4 предмета одним действием, холдер «Пусто», кнопка disabled |
| 15.5 | Corpse buttons | pass | У трупа только «Осмотреть» |

### Section 6: Master Panel (смоук)

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 6.1 | Worlds tab | pass | RU-названия миров, editable (Форк+Удалить) vs library (Форк) |
| 6.5 | Sessions list | pass | Сессия видна, «Управление» открывает session view |
| 6.7 | Edit creature HP | pass | Player HP 3→12 через форму, таблица обновилась |
| 6.11 | Save and load | pass | Именованный сейв + load с подтверждением; смерть gretta пережила load |

### Auto-discovered scenarios (аудит-фиксы)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Hostility в perception после рефакторинга `_hostility_from_relation` | awareness_builder quick-fix | pass | Противники в бою помечены верно, труп не hostile, после боя aldric снова FRIENDLY |
| Реакции/OA end-to-end | transport_payloads rename | pass | NPC OA отработал; player-side prompt (`reaction_to_dict`) покрыт юнитами `test_reaction_wiring.py` — детерминированно застейджить его в UI нечем (RuleBrain-melee не покидает reach игрока) |
| `faction_hostility_check` уровень лога | фаза 1 | pass | В full.jsonl только DEBUG-записи |
| Гейт чужих ошибок в логе игрока | фаза 1 (build_action_result) | pass | Свои отказы видны («Цель слишком далеко (25 ft, досягаемость 5 ft)»), чужих технических отказов в логе нет |
| Props-карточки предметов | спринт 024 фаза 3 | pass | RU-карточки weapon/armor/shield/potion/accessory в инвентаре и торговле |

## Quick Fixes

Нет.

## Findings

### Blockers

Нет.

### Minor

- **`loot-panel-raw-title`** — LootPanel всё ещё вешает английский `describe_item()` в native `title`
  (`Frost Dagger (weapon: 1d4 piercing, reach 5ft [finesse, magic, +1])`). Фаза 3 покрыла 4 точки рендера
  (инвентарь bag+слоты, торговля buy+sell), панель добычи — пятая, пропущенная. Кандидат в бэклог к `item-properties-ui`.
- **`potion-zero-heal-message`** — зелье на полном HP: «Ты используешь Зелье лечения (восстановлено 0 HP)».
  Тот же паттерн, что фаза 1 чинила для Second Wind, но в перцепторе use_item. Плюс «HP» латиницей при «ОЗ» везде.
- **`npc-move-log-not-localized`** — движение NPC в логе по-английски: «Ser Aldric moved (10 ft)» при полностью
  RU-логе остальных событий.
- **`ru-duplicate-condition-label`** — в форме редактирования существа две кнопки состояний «Оглушён»
  (Stunned и Deafened переведены одинаково).
- **`nearby-shows-raw-id`** — панель «Поблизости» показывает raw id (marta, gretta, aldric) вместо display name
  («Гретта Торговка», «Сэр Олдрик» — имена есть, master-таблица и inspect-модалка их показывают). Лог событий
  говорит «человек говорит» — третий вариант именования того же NPC. Часть кластера `ui-language-mixing`.
- **`master-player-brain-label`** — в master-таблице существ у игрока ИИ показан как `rule_based` (реально PlayerBrain).
- **`round-stop-timeout-on-disconnect`** — при закрытии вкладки игрока в мирном режиме первый `stop_round`
  упёрся в 5s-таймаут (`stop_round_timeout` + `disconnect_stop_failed`, level=error), но eviction-проход через
  1.5s остановил round-тред штатно, сессия осталась загружаемой. Похоже, stop не будит поток, ждущий действия
  игрока; самоизлечилось через grace-path. Смежно с бэклог-айтемом `save-round-concurrency`.
  Бонус-находка: `exc_info: true` не рендерится в JSON-лог — стек `disconnect_stop_failed` потерян.

### Observations (не баги)

- Дважды за прогон подряд идущие d20 одного актёра в одном раунде совпали (3/3 у игрока, 15/15 у aldric
  turn-attack + OA). Все три rng-пути Round используют один общий `dice_rng`, так что это почти наверняка
  совпадение (p≈1/20 на пару), но если паттерн вернётся — стоит юнитом прогнать attack+OA в одном раунде.
- Цены торговца — авторские (обычный Dagger 200g при SRD 2g в каталоге); продажа Longsword идёт по SRD 15g.
  Выглядит намеренно (magic-shop наценка), но разница x100 на немагическом кинжале бросается в глаза.
- Combat-панель показывает «Оружие: flaming slash (1d8)» без огненного 1d6 — карточка предмета и лог урона
  полные, сокращение только в этой строке.

## Log Analysis

- Единственные error-записи — пара `stop_round_timeout`/`disconnect_stop_failed` (см. Findings), других
  exceptions/tracebacks нет.
- `faction_hostility_check` только на DEBUG (фаза 1 подтверждена).
- `action_failed` по дальности логируется на INFO с локализованным сообщением — согласуется с UI.
