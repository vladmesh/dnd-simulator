# Backlog

## Bugs

### move/dash не перемещает в бою
`dash toward <target>` возвращает "Moved" но позиция на battle map не меняется.
Баг в game engine (`combat_manager.resolve_move` / `move_toward`), не в API.
Нужно дебажить логику `move_toward()` — возможно коллизия стен или ошибка в расчёте новой позиции.

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

## Refactoring

### world-builder.js — разбить на модули
Файл 1700+ строк, 7 рендер-функций с копипастой паттерна "список карточек + CRUD-форма".
Выделить общий `CrudStep` (список + add/edit/delete + auto-slug).
Вынести form-builder helpers (translatableField, connectionEditor, neighborEditor).
Разбить на файлы по шагам если появится bundler, или хотя бы на логические секции с чёткими границами.
