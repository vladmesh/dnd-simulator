# Task: Minimal Test World for Integration Tests

**Date:** 2026-03-24
**Sprint:** 002-meta-pipeline
**Phase:** 1 — Integration Tests

## Description

Создать минимальный мир для интеграционных тестов в `tests/integration/content/`. Мир должен быть достаточным для полного цикла: создание сессии → создание игрока → бой → результат.

Состав:
- 1 регион, 1 локация (tavern или arena)
- 1 NPC с rule brain, базовыми статами, оружием
- Определение игрока (стартовая локация, начальное оружие)
- Без LLM зависимостей (все brain: rule_based)

Формат: directory-based (world.yaml, regions.yaml, npcs.yaml, locations.yaml) — консистентно с основным контентом.

**Файлы:** `tests/integration/content/test_world/`

## Acceptance Criteria

- [ ] `content_loader` успешно загружает тестовый мир
- [ ] NPC и игрок оказываются в одной локации (для тестирования боя)
- [ ] Все brain = rule_based, никаких LLM зависимостей
- [ ] Минимален: ничего лишнего, только то что нужно для тестовых сценариев

## Status

`done`

## Developer Notes

Не создавали новый контент — скопировали три существующих мира (arena, village, sneak_test) с одним изменением: paladin `ai: llm` → `ai: rule`. Миры уже писались под тесты, покрывают: combat (arena — 4 бойца, оружие, броня, зелья, battle map со стенами), schedules (village — 5 NPC с ролями, 8 локаций, settlement), sneak attack (sneak_test — минимальная арена).

Также добавили `DND_CONTENT_DIR` env var в app.py для подстановки тестового контента в compose. `GameService` уже принимал `content_dir` — нужно было только пробросить из env.
