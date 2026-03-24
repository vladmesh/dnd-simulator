# Backlog

## Bugs

### Персонаж создаётся без атак
`POST /api/player/sessions/{id}/character` не принимает поле `attacks`.
Персонаж дерётся кулаками (1 урон). Добавить `attacks` в `CreatePlayerRequest` и `parse_player`.

### `look` через action — English hardcode
`_cmd_look` в GameService использует хардкод-строки ("Terrain:", "Weather:"), а не `_()`.
Не критично — perception API отдаёт сырые данные, фронт переведёт.
Но для консистентности text-based команд стоит перевести.

## Features

### Periodic autosave scheduler
Фоновый asyncio таск в FastAPI lifespan: каждые 2 минуты вызывает
`service.autosave_all_sessions()`. Дополняет существующий per-action автосейв
и shutdown автосейв. Использовать `asyncio.create_task` с loop + sleep,
cancel на shutdown перед финальным autosave.

### NPC реагируют на say мгновенно
После `say` команды тикнуть NPC в локации (1 раунд), чтобы RuleBrain/LlmBrain
успел ответить в рамках того же запроса. Сейчас NPC отвечают только при advance_time.
`list_npcs` итерирует по регионам и ищет NPC в каждом.
NPC в несуществующем регионе не попадёт в список. Мелочь, но стоит поправить —
итерировать по entities напрямую.

### ~~Flaky initiative test~~ ✅ FIXED
~~`test_second_attack_does_not_reroll_initiative` падает рандомно~~ — причина: атаки убивали
c2 (AC=12), удаляя из turn_order. Фикс: AC=30 чтобы атаки всегда мазали.

### `go`/travel реализован как хак через `wait`
`LocationPanel` шлёт `Action(name=WAIT, params={hours: 0, travel_to: location_id})`.
Нужен отдельный `ActionType.TRAVEL` с собственным хендлером, валидацией маршрута и расчётом времени.

### `inspect` реализован как параметр `idle`
`CombatPanel`/`Perception` шлют `Action(name=IDLE, params={inspect_target: entity_id})`.
Inspect должен быть отдельным query или free action, а не неявным параметром idle.

## Features

### Master panel: отображение inventory и equipped weapon
`CreatureResponse` и `all_entities` query не включают inventory/equipped_weapon.
Мастер не видит какие предметы у существ. Добавить поля в схему и query.

### Master panel: UI для give_item
Endpoint `POST /api/master/sessions/{id}/creatures/{entity_id}/items` есть, но кнопки нет.
Добавить в карточку существа кнопку «Дать предмет» с формой (тип, название, параметры).

## Performance

### Awareness rebuild — кэширование и инвалидация

**Проблема:** `build_awareness()` делает 4-5 query к нижним слоям (geography, settlements, politics) при каждом вызове. Сейчас вызывается перед каждым ходом каждого существа — O(N) rebuilds за раунд. При масштабировании до десятков NPC с LlmBrain станет bottleneck: каждый query — dict lookup + копирование, а для LlmBrain результат ещё сериализуется в промпт.

**Что дорого и почему:**
- weather + region_info (2 query) — меняются раз в tick Geography, одинаковы для всех в регионе
- settlements (1 query) — меняются раз в 30 дней, одинаковы для региона
- politics + nation_info (2 query) — меняются раз в 30 дней, одинаковы для региона
- nearby entities — O(N) scan, уникально per creature, но меняется только когда в локации что-то произошло

**Решение в два слоя:**

1. **WorldSnapshot (per region, per tick)** — frozen dataclass с weather, region_name, settlements, politics. Строится один раз при `advance_time()`, кэшируется по `(region_id, tick_number)`. Все существа в регионе берут готовый snapshot вместо 5 query. Инвалидация тривиальна: новый tick = новый snapshot.

2. **Dirty flag per location для nearby entities** — действие в локации X помечает awareness всех существ в X как stale. `build_awareness()` проверяет флаг: чисто → кэш, грязно → пересобрать только nearby (не query к слоям). Существа в других локациях не затронуты.

**Когда делать:** когда начнёт тормозить (>20 NPC с LlmBrain в одном мире). API awareness не меняется — те же PeacefulAwareness/CombatAwareness, просто собираются быстрее. Ничто из уровней 1-3 (conditions, inventory, spells) на это не завязано.

## Refactoring

### world-builder.js — разбить на модули
Файл 1700+ строк, 7 рендер-функций с копипастой паттерна "список карточек + CRUD-форма".
Выделить общий `CrudStep` (список + add/edit/delete + auto-slug).
Вынести form-builder helpers (translatableField, connectionEditor, neighborEditor).
Разбить на файлы по шагам если появится bundler, или хотя бы на логические секции с чёткими границами.
