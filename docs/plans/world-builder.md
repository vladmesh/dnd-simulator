# World Builder — создание миров через UI

## Context

Сейчас миры создаются только правкой YAML на диске. Нужен UI-визард в панели мастера для создания миров послойно: от географии до NPC.

## Подход

Wizard-стиль: пошаговые вкладки, каждая — один слой. Данные накапливаются на клиенте, на финальном шаге — `POST /api/master/worlds` всей структуры. Бэкенд сохраняет в directory format.

## API: `POST /api/master/worlds`

Принимает полную структуру мира (id, name, description, regions, locations, nations, npcs). Сохраняет в `content/worlds/{id}/` как набор YAML файлов.

## UI Wizard (7 шагов)

1. **Мир** — id, name, description
2. **Регионы** — terrain, coordinates, elevation, water_proximity, connections
3. **Поселения** — type, population, prosperity, defenses (сгруппированы по регионам)
4. **Локации** — привязка к регионам/поселениям, neighbors, auto-generate
5. **Нации** — regions, wealth/military/stability, leader
6. **NPC** — role, personality, stats, attacks, brain type, привязка к settlement/location
7. **Обзор** — JSON preview, кнопка создания

## Файлы

- `src/dnd_simulator/content_saver.py` — сериализация dict → YAML
- `src/dnd_simulator/adapters/api/schemas.py` — Pydantic модели
- `src/dnd_simulator/service/` — create_world метод
- `src/dnd_simulator/adapters/api/routes_master.py` — POST endpoint
- `static/js/api.js`, `static/master.html`, `static/js/master.js` — UI
