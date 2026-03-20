# API Brainstorm

## Решения

### Транспорт
- **REST** для всего (пошаговый режим = request/response по природе)
- WebSocket — потом, когда/если появится realtime (мир тикает сам между ходами)
- LLM-стриминг: пока без него, если надо — SSE на отдельном эндпоинте

### Фреймворк
- **FastAPI** (async, OpenAPI из коробки, WebSocket-поддержка на будущее)

### Хранение данных
- **В оперативке** во время сессии, **YAML на диске** как персистентный формат
- БД не нужна: один процесс, нет конкурентного доступа, объём данных мал
- Многопользовательность на уровне сервера (каждый игрок — свой инстанс мира)
- 10-100 игроков — без проблем (~5 MB RAM на инстанс), узкое место — LLM rate limits

### Структура файлов

```
content/worlds/{world_name}/      ← шаблон мира (мастер создаёт, версионируется)
    world.yaml                     ← мета: name, description
    regions.yaml                   ← география (immutable после старта)
    nations.yaml                   ← стартовые значения
    settlements.yaml               ← стартовые значения
    npcs.yaml                      ← стартовые NPC
    (нет player.yaml — игрок создаётся при входе в сессию)

saves/{session_id}/               ← рабочая копия запущенной сессии
    world.yaml                     ← время, тики
    regions.yaml                   ← копия из шаблона (read-only)
    nations.yaml                   ← текущее состояние
    settlements.yaml               ← текущее состояние
    npcs.yaml                      ← ВСЕ NPC (включая добавленных мастером)
    player.yaml                    ← создаётся игроком при входе
```

Шаблон — чистый, из него можно запускать сколько угодно сессий.
Сессия — самодостаточная рабочая копия.

### Два режима редактирования мира

**Между сессиями (файлы на диске)** — основной режим. Сервер выключен или сессия не активна, никаких гонок:
- Регионы, связи, terrain
- Нации, поселения (полная структура)
- NPC (полный CRUD, статблоки, personality, brain)
- Баланс

**Во время сессии (hot controls, в памяти)** — DM-импровизация за ширмой:
- Спавн/удаление NPC
- HP, золото, позиция
- Переключение brain
- Advance time
- НЕ структурные изменения (регионы, связи)

### Аутентификация
- Пока нет, single-user режим, два режима (мастер/игрок) без логина

### Создание персонажа
- Игрок создаёт персонажа при входе в сессию, не на уровне шаблона мира
- `POST /api/player/sessions/{id}/character` — создание персонажа

### Два режима — эндпоинты

**Мастер — шаблоны (между сессиями):**

```
POST   /api/master/worlds                         — создать мир (шаблон)
GET    /api/master/worlds                         — список миров
GET    /api/master/worlds/{id}                    — полный шаблон
PUT    /api/master/worlds/{id}/regions             — задать регионы
PUT    /api/master/worlds/{id}/nations             — задать нации
PUT    /api/master/worlds/{id}/settlements         — задать поселения
CRUD   /api/master/worlds/{id}/npcs                — управление NPC шаблона
```

**Мастер — живая сессия (hot controls):**

```
POST   /api/master/sessions                       — запустить мир (копирует шаблон)
DELETE /api/master/sessions/{id}                  — остановить
GET    /api/master/sessions/{id}                  — god-mode стейт

# Hot controls (память, мгновенный эффект)
POST   /api/master/sessions/{id}/npcs              — спавн NPC
DELETE /api/master/sessions/{id}/npcs/{nid}        — убрать NPC
PATCH  /api/master/sessions/{id}/npcs/{nid}        — HP, позиция, brain
PUT    /api/master/sessions/{id}/npcs/{nid}/brain  — переключить brain
PATCH  /api/master/sessions/{id}/nations/{nid}     — wealth, military, stability
PATCH  /api/master/sessions/{id}/settlements/{sid} — population, prosperity
PATCH  /api/master/sessions/{id}/player            — HP, золото
POST   /api/master/sessions/{id}/time/advance      — продвинуть время

# Персистентность
POST   /api/master/sessions/{id}/save              — сбросить состояние на диск
```

**Игрок:**

```
POST   /api/player/sessions/{id}/character         — создать персонажа
GET    /api/player/sessions/{id}/status            — HP, золото, позиция
POST   /api/player/sessions/{id}/action            — действие
GET    /api/player/sessions/{id}/perception        — что видит персонаж
GET    /api/player/sessions/{id}/events            — новые события
GET    /api/player/sessions/{id}/map               — карта связей региона
GET    /api/player/sessions/{id}/combat            — инициатива, позиции, раунд
```

### Mutability

| Сущность   | Immutable (при создании)          | Hot controls (в рантайме)                       |
|------------|-----------------------------------|-------------------------------------------------|
| Region     | terrain, lat/lon, elevation, conn | — (погода автоматическая)                       |
| Nation     | name, regions                     | wealth, military, stability                     |
| Settlement | name, region_id, type             | population, prosperity, defenses                |
| NPC        | name, race, class                 | hp, ac, gold, personality, brain, region         |
| Player     | name, race, class, alignment      | hp, ac, gold, region_id                         |

## Итерации

### Итерация 1 — Скелет ✅
- FastAPI-адаптер, базовая структура
- SessionManager (создать/получить сессию)
- `POST /api/player/sessions/{id}/action` — действие игрока
- `GET /api/player/sessions/{id}/status` — статус персонажа
- `POST /api/master/sessions` — создать сессию
- `GET /api/master/sessions/{id}` — god-mode стейт
- `make serve` — запуск сервера

### Итерация 2 — Мастер CRUD + структура файлов
- Разбить монолитный YAML на отдельные файлы (world/regions/nations/settlements/npcs)
- ContentLoader: поддержка нового формата (директория вместо одного файла)
- Мастер: CRUD шаблонов мира (файловые операции)
- Мастер: hot controls живой сессии (NPC спавн/удаление, HP, brain)
- Сессия: копирование шаблона → saves/{session_id}/
- Сессия: save (сброс памяти на диск)

### Итерация 3 — Полный игрок
- Создание персонажа при входе в сессию
- Perception, events, combat, map
- Все игровые действия через REST

### Итерация 4 — Полировка
- Валидация, ошибки, i18n в ответах
- Восстановление сессии из сейва при рестарте сервера
