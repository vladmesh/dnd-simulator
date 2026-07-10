# Task: World seed plumbing — единый сид раздаётся слоям

**Date:** 2026-07-10
**Sprint:** 021-save-schema
**Phase:** 1 — RNG threading & determinism

## Description

Ввести единый world seed и раздать его слоям через конструкторы. Сейчас seed-параметры частично существуют, но не подключены:

- `layers/politics/layer.py:94` — `self._rng = random.Random(seed)`, но `service/game_service.py:148` не передаёт seed → всегда unseeded.
- `layers/geography/weather.py:187` — `WeatherEngine.__init__(seed)` прокинут из `GeographyLayer(weather_seed=...)`, но game_service его тоже не передаёт.
- `layers/ecology/layer.py:32-49` — seed-параметра нет вообще, добавить `seed: int | None = None` → `self._rng = random.Random(seed)`.
- `layers/entities/layer.py` — добавить такой же `seed` → `self._rng` (потребитель — encounter rolls, подключается в task 2; в этой таске достаточно, что RNG существует и детерминирован).

Схема раздачи: game_service при сборке мира читает env `DND_WORLD_SEED` (int). Если не задан — генерирует случайный и логирует (structlog), чтобы любой прогон был воспроизводим постфактум. Из world seed детерминированно выводятся слоевые сиды — фиксированная схема `random.Random(f"{world_seed}:{layer_name}")`-style или последовательный draw из `random.Random(world_seed)` в фиксированном порядке слоёв; главное требование — разные слои получают разные потоки, одинаковый world seed даёт одинаковый набор слоевых сидов. World seed сохранить как атрибут `World` (понадобится phase 2 для записи в сейв).

`rules/dice.py` / `DND_DICE_SEED` не трогать — dice-RNG остаётся отдельным потоком (решение в sprint.md).

## Tests First

- Два `PoliticsLayer` с одним seed при одинаковой стартовой конфигурации наций дают идентичную последовательность дипломатических/военных исходов за N тиков; с разными seed — последовательности расходятся (хотя бы одно отличие на достаточном N).
- Два `WeatherEngine` (или `GeographyLayer` целиком) с одним seed дают идентичную последовательность погоды за N часов; с разными — расходятся.
- Мир, собранный через game_service дважды при `DND_WORLD_SEED=42` (monkeypatch env), получает одинаковые слоевые сиды: первые K значений `layer._rng.random()` каждого слоя совпадают между сборками.
- Слоевые сиды различны между слоями: при одном world seed потоки politics и ecology не совпадают.

## Implementation

После красных тестов: параметр `seed` в `EcologyLayer`/`EntitiesLayer`, вывод слоевых сидов в одном месте (helper рядом со сборкой мира в `service/game_service.py`), проводка в конструкторы всех четырёх слоёв (settlements — если там есть случайность; если нет, не добавлять пустой параметр), `World.seed` атрибут. Env-доки: упомянуть `DND_WORLD_SEED` в CLAUDE.md рядом с `DND_DICE_SEED`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check-backend`)
- [ ] `DND_WORLD_SEED` документирован; незаданный seed логируется при сборке мира
- [ ] Один world seed → воспроизводимые и попарно различные слоевые потоки

## Status

`done`

## Developer Notes

Added `DND_WORLD_SEED` handling in `GameService`, deterministic layer seed derivation, and `World.seed`.
`EcologyLayer` and `EntitiesLayer` now own constructor-seeded RNGs; politics/weather receive derived seeds through the existing constructors.
The RED point was the service-built world lacking `World.seed` and layer RNG plumbing; existing politics/weather seed behavior was already deterministic.
