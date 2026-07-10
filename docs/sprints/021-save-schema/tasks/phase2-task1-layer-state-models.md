# Task: Типизированные state-модели простых слоёв + RNG в состоянии

**Date:** 2026-07-10
**Sprint:** 021-save-schema
**Phase:** 2 — Unified Pydantic save schema

## Description

Каждый из четырёх «простых» слоёв (geography, politics, settlements, ecology) получает Pydantic-модель своего состояния как единственный source of truth формата: `GeographyState`, `PoliticsState`, `SettlementsState`, `EcologyState`. Сейчас `get_state()`/`load_state()` руками собирают/разбирают вложенные dict-ы (`layers/geography/layer.py:208`, `layers/politics/layer.py:343` — включая склейку tuple-ключей в `"a:b"`, `layers/settlements/layer.py:181`, `layers/ecology/layer.py:163`).

Архитектурное ограничение: сигнатура `Layer.get_state() -> dict` / `load_state(dict)` в `core/layer.py` НЕ меняется (core остаётся без pydantic). Модели живут в `models.py` (или `state.py`) соответствующего слоя; `get_state` возвращает `Model.model_dump(mode="json")`, `load_state` начинается с `Model.model_validate(data)` — рукописный парсинг с `.get(..., default)` внутри слоёв удаляется. Валидационная ошибка при загрузке — fail-fast (пусть падает понятным `ValidationError`), не тихий дефолт.

Состояние RNG: слои, владеющие `random.Random` (politics `_rng`, ecology `_rng`, geography `WeatherEngine`, entities — в task 2), сериализуют `rng.getstate()` в своё состояние (tuple → списки JSON-совместимо) и восстанавливают через `setstate` в `load_state`. Загрузка сейва продолжает ту же случайную последовательность, а не начинает новую с сида.

## Tests First

- Round-trip каждого слоя: наполненный слой → `get_state()` → JSON-сериализация → `load_state()` в свежий инстанс → `get_state()` идентичен; поведение после загрузки идентично поведению оригинала (следующие N тиков/дро совпадают).
- Продолжение RNG: слой с seed делает K дро → save → load в новый инстанс → следующие M дро совпадают с непрерывным прогоном K+M на оригинале (politics: следующие дипломатические исходы; ecology: следующие roam-выборы; geography: следующая погода).
- Невалидное состояние (отсутствующее обязательное поле, мусорный тип) → `ValidationError`, не тихая деградация.
- Politics: пары фракций с отношениями и war_durations переживают round-trip без потери (tuple-ключи).

## Implementation

После красных тестов: модели состояний по слоям, общий helper для сериализации `Random.getstate()`/`setstate()` (один, переиспользуемый — например в `layers/common/rng_state.py` или рядом с Layer-утилитами, но НЕ в core), замена тел `get_state`/`load_state`. Существующие тесты слоёв обновить на новый формат, если они пиновали сырые dict-ключи. Формат поля времени `GameDateTime` — переиспользовать существующие `to_dict`/`from_dict` через кастомный сериализатор или submodel.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check-backend`)
- [ ] В get_state/load_state четырёх слоёв нет рукописной сборки dict-ов и `.get(..., default)`
- [ ] RNG-состояние каждого слоя переживает save/load и продолжает последовательность

## Status

`pending`
