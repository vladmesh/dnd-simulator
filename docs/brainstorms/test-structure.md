# Обзор тестов и план структурирования

## Текущее состояние

**628 тестов**, все проходят за **~5 секунд**. Всё лежит в одной плоской директории `tests/`, без маркеров, без разделения. Хуков и CI нет.

### Классификация текущих тестов

| Категория | Файлы | Тестов (≈) | Характер |
|-----------|-------|-----------|----------|
| **Чистые юнит** | `test_dice`, `test_character`, `test_geography_formulas`, `test_politics_formulas`, `test_settlements_formulas`, `test_checks`, `test_combat`, `test_conditions`, `test_battle_map`, `test_validation`, `test_placeholder` | ~220 | Чистая логика, никаких I/O, мгновенно |
| **Компонентные** | `test_action_dispatcher`, `test_game_loop`, `test_initiative`, `test_movement`, `test_multi_action`, `test_combat_awareness`, `test_perception`, `test_double_turn_bug`, `test_npc_layer`, `test_geography_layer`, `test_politics_layer`, `test_settlements_layer`, `test_npc_tools`, `test_rule_brain`, `test_player_brain`, `test_summarizer`, `test_geography_weather` | ~350 | Собирают граф объектов, но без I/O — тоже быстрые |
| **API + WS** | `test_api`, `test_ws` | ~50 | FastAPI `TestClient` (in-process), `tmp_path` для store |
| **Контент** | `test_content_loader_dir` | ~5 | Читает YAML с диска |

> [!IMPORTANT]
> Все 628 тестов сейчас бегут за 5 сек. Даже «тяжёлые» API-тесты — in-process через TestClient. Настоящих интеграционных тестов (поднятие стека, реальный HTTP/WS) и e2e пока нет.

---

## Мои мысли по предложенной структуре

### 1. `make format` → git pre-commit hook ✅

Отличная идея. Рекомендую через `pre-commit` фреймворк:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ruff-format
        name: ruff format
        entry: uv run ruff format
        language: system
        types: [python]
      - id: ruff-fix
        name: ruff fix
        entry: uv run ruff check --fix
        language: system
        types: [python]
```

**Нюанс**: `pre-commit` умеет работать только с staged файлами (`--from-ref/--to-ref`), авто-добавлять исправления в коммит можно, но это опасно — можно случайно закоммитить лишнее. Безопаснее: хук форматит staged files и если что-то поменялось — `git add -u` отформатированные файлы. Или ещё проще — просто падать если форматирование сломано (как в варианте 2) и форматировать руками.

### 2. `make lint` + `make unit-tests` → pre-push hook ✅

Полностью согласен. Ключевой вопрос — **что считать unit**:

**Моя рекомендация**: юнит = всё, что не требует I/O и поднятия стека. Сейчас это **все 628 тестов** (даже API тесты in-process). Я бы на текущем этапе разделил маркерами:

```python
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "unit: Pure unit tests, no I/O",
    "integration: Requires running stack",
    "e2e: End-to-end scenario tests",
]
```

И добавил бы маркер `integration` только тем тестам, которые реально поднимают стек. Все остальные — unit по умолчанию.

```makefile
unit-tests:
	uv run pytest -m "not integration and not e2e" -q

integration-tests:
	uv run pytest -m "integration" -q
```

**Или без маркеров**, через директории:

```
tests/
  unit/           ← всё что есть сейчас
  integration/    ← новые тесты с поднятием стека
  e2e/            ← сценарии (если будут)
```

Преимущество директорий — не нужно помнить о маркерах. Но можно и комбинировать.

### 3. `make integration-tests` — тесты с поднятием стека ✅

Согласен, это отдельный слой. Сюда пойдут:

- **REST тесты к реальному серверу** (requests/httpx к `localhost:8001`)
- **WebSocket тесты** (через `websocket-client` к реальному серверу)
- **Playwright/browser** (фронт + бек)

> [!TIP]
> **Docker-обёртка** — отличная идея. Простой `docker-compose.test.yml` который поднимает бек + фронт и гоняет тесты в отдельном контейнере. Это решает проблему с мусором на хосте и делает CI-ready.

```makefile
integration-tests:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

# или без докера для локальной разработки:
integration-tests-local:
	uv run pytest tests/integration/ -q
```

### 4. E2E через AI агента — интересная идея, но с оговорками ⚠️

Идея в том, что D&D симулятор слишком недетерминирован для классических ассертов — кубики, ИИ решения, стохастичность. Пусть AI-агент анализирует, логична ли последовательность событий.

**Плюсы:**
- Действительно обходит проблему случайности
- Можно проверять семантику, а не точные значения

**Минусы / Риски:**
- Flaky по определению — LLM может дать разный вердикт
- Дорого (API calls)
- Сложно отлаживать: "AI сказал что баг" — а баг ли?

**Мои рекомендации:**
1. Для **механик с кубиками** — лучше seed-based тесты. Всё уже есть (`rng=random.Random(42)`). Это надёжнее.
2. **AI-агент** — хорош для **smoke-тестов полного сценария**: "создай сессию → создай персонажа → пройди 10 раундов → проверь что всё не упало и результаты осмысленны". Но не как основной инструмент тестирования.
3. Можно оформить как **отдельный скрипт** `scripts/e2e_ai_check.py` который запускается вручную или по расписанию.

---

## Итоговый план Makefile

```makefile
# === Качество кода ===
format:         # Форматирование ruff
lint:           # ruff check + ruff format --check
typecheck:      # mypy

# === Тесты ===
unit-tests:     # Быстрые, без I/O (~5 сек)
integration-tests:  # С поднятием стека
e2e:            # AI-powered smoke tests (опционально)

# === Комбо ===
check-fast: lint typecheck unit-tests      # pre-push
check: lint typecheck unit-tests integration-tests  # полная проверка
```

## Итоговый план хуков

| Хук | Что делает | Как |
|-----|-----------|-----|
| `pre-commit` | `ruff format --check` + `ruff check` на staged файлах. Если сломано — fallback `ruff format` + `ruff check --fix` + `git add` | `.pre-commit-config.yaml` или кастомный скрипт |
| `pre-push` | `make lint` + `make unit-tests` | `.githooks/pre-push` |

---

## Вопросы к тебе

1. **Директории vs маркеры** — как разделять тесты? Я склоняюсь к директориям (`tests/unit/`, `tests/integration/`), но можем и маркерами.
2. **API/WS тесты** — сейчас они in-process через TestClient и бегут за ~1 сек. Оставить их в unit или вынести в integration? Я бы оставил в unit, а в integration положил бы тесты к реальному поднятому серверу.
3. **pre-commit**: авто-фикс + `git add` (твой вариант) или просто fail если не отформатировано?
