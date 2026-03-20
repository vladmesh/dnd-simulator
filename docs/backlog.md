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

### NPC list не показывает NPC вне регионов
`list_npcs` итерирует по регионам и ищет NPC в каждом.
NPC в несуществующем регионе не попадёт в список. Мелочь, но стоит поправить —
итерировать по entities напрямую.
