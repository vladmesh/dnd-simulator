# API Brainstorm

## Решения

### Транспорт
- **REST** для всего (пошаговый режим = request/response по природе)
- WebSocket — потом, когда/если появится realtime (мир тикает сам между ходами)
- LLM-стриминг: пока без него, если надо — SSE на отдельном эндпоинте

### Фреймворк
- **FastAPI** (async, OpenAPI из коробки, WebSocket-поддержка на будущее)

### Хранение данных
- **В оперативке**, сериализация на диск (JSON) — как сейчас
- БД не нужна: один процесс, нет конкурентного доступа, объём данных мал
- Autosave после каждого действия, восстановление из сейва при рестарте
- Многопользовательность на уровне сервера (каждый игрок — свой инстанс мира)
- 10-100 игроков — без проблем (~5 MB RAM на инстанс), узкое место — LLM rate limits

### Аутентификация
- Пока нет, single-user режим, два режима (мастер/игрок) без логина

### Два режима

**Мастер** — полный контроль над миром:

```
# Миры (конфигурация)
POST   /api/master/worlds                         — создать мир
GET    /api/master/worlds                         — список миров
GET    /api/master/worlds/{id}                    — полный стейт

# Сессии (запущенный инстанс мира)
POST   /api/master/sessions                       — запустить мир
DELETE /api/master/sessions/{id}                  — остановить
GET    /api/master/sessions/{id}                  — god-mode стейт

# Регионы (read-only после создания)
GET    /api/master/sessions/{id}/regions
GET    /api/master/sessions/{id}/regions/{rid}

# Нации (wealth, military, stability — editable)
GET    /api/master/sessions/{id}/nations
PATCH  /api/master/sessions/{id}/nations/{nid}

# Поселения (population, prosperity, defenses — editable)
GET    /api/master/sessions/{id}/settlements
PATCH  /api/master/sessions/{id}/settlements/{sid}

# NPC — полный CRUD
GET    /api/master/sessions/{id}/npcs
POST   /api/master/sessions/{id}/npcs              — добавить на лету
GET    /api/master/sessions/{id}/npcs/{nid}
PATCH  /api/master/sessions/{id}/npcs/{nid}        — personality, brain, hp, gold...
DELETE /api/master/sessions/{id}/npcs/{nid}

# Brain — отдельный эндпоинт (инстанциация класса + выбор модели)
PUT    /api/master/sessions/{id}/npcs/{nid}/brain
       {"type": "rule_based"}
       {"type": "llm", "model": "deepseek/deepseek-chat-v3-0324"}

# Игрок
GET    /api/master/sessions/{id}/player
PATCH  /api/master/sessions/{id}/player

# Сейвы
GET    /api/master/sessions/{id}/saves
POST   /api/master/sessions/{id}/saves
POST   /api/master/sessions/{id}/saves/{name}/load

# Время
POST   /api/master/sessions/{id}/time/advance      {"hours": 6}
```

**Игрок** — только своя перспектива (через perceive(), фильтрованные события):

```
# Восприятие
GET    /api/player/sessions/{id}/perception        — что видит персонаж
GET    /api/player/sessions/{id}/events            — новые события
GET    /api/player/sessions/{id}/status            — HP, золото, позиция

# Действия
POST   /api/player/sessions/{id}/action            — {"action": "attack goblin"}
GET    /api/player/sessions/{id}/map               — карта связей региона

# Бой
GET    /api/player/sessions/{id}/combat            — инициатива, позиции, раунд
```

### Mutability

| Сущность   | Immutable (при создании)          | Editable (мастер в рантайме)                    |
|------------|-----------------------------------|-------------------------------------------------|
| Region     | terrain, lat/lon, elevation, conn | — (погода автоматическая)                       |
| Nation     | name, regions                     | wealth, military, stability, leader             |
| Settlement | name, region_id, type             | population, prosperity, defenses                |
| NPC        | name, race, class                 | hp, ac, gold, personality, brain, attacks, region |
| Player     | name, race, class, alignment      | hp, ac, gold, region_id                         |

## Итерации

### Итерация 1 — Скелет
- FastAPI-адаптер, базовая структура
- SessionManager (создать/получить сессию)
- `POST /api/player/sessions/{id}/action` — действие игрока
- `GET /api/player/sessions/{id}/status` — статус персонажа
- `POST /api/master/sessions` — создать сессию
- `GET /api/master/sessions/{id}` — god-mode стейт
- Проверить через Swagger UI

### Итерация 2 — Мастер CRUD
- NPC CRUD (add/get/patch/delete)
- Brain switching (PUT)
- Нации, поселения (GET/PATCH)
- Регионы (GET)

### Итерация 3 — Полный игрок
- Perception, events, combat, map
- Все игровые действия через REST

### Итерация 4 — Полировка
- Сейвы через API
- Время (advance)
- Валидация, ошибки, i18n в ответах
