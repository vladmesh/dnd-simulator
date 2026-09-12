# Sprint Pipeline

С 2026-09-12 спринты проекта ведёт общий контур секретаря. Собственная спринтовая машинерия репозитория
(скиллы `go`, `new-sprint`, `plan-phase`, `implement`, `close-phase`, `close-sprint`, `meta-go`, файлы
`docs/sprints/`, `docs/STATUS.md` как источник состояния) снята; её история лежит в knowledge инстанса,
`state/knowledge/projects/dnd-simulator/`.

## Как это устроено

- **Спринт** — сущность на доске секретаря: одна фраза цели (конечное состояние продукта), Definition of
  Done из проверяемых пунктов, резервируемые проекты, наблюдатель. Открывает PO скиллом `open-sprint`
  после гриля развилок. Фаз и пула задач нет: путь к цели переписывается на каждом шаге.
- **Наблюдатель** (голова из `heads.yaml`) режет ровно одну карточку за раз из текущего понимания,
  разбирает Assessment и Blocked, пишет resume в сущность спринта. Скилл `observe-sprint`.
- **Карточка** — спека Goal / Context / Acceptance criteria / Out of scope. Воркер поднимает воркспейс
  из карточки и не видит этого разговора, поэтому Context содержит указатели на файлы репозитория.
  Скилл `spec-card`. Code-карточки в проекте строго последовательны (`code_concurrency: 1`).
- **Validate** — механический гейт: адаптер `secretary-instance/adapters/dnd-simulator.yaml`
  (setup `make install`, smoke один быстрый unit-файл, `broad_check` = `pytest tests/unit`), GitHub CI
  как `validation.ci`, затем LLM-ревью карточки. Assessment ждёт решения наблюдателя: release, rework
  или reslice.
- **Состояние** читается из данных: `sprint status`, `task list --sprint`. Указатели — в
  [STATUS.md](STATUS.md).

## Что остаётся в репозитории

- Живые документы: [VISION.md](VISION.md), [ROADMAP.md](ROADMAP.md), [BACKLOG.md](BACKLOG.md),
  брейнштормы и планы в `docs/brainstorms/`, `docs/plans/`. `open-sprint` читает ROADMAP и VISION как
  вход; BACKLOG — сырьё для карточек наблюдателя, не план.
- Доменные скиллы: `/e2e` (Playwright-регресс по [e2e-playbook.md](e2e-playbook.md), отчёт в
  `/tmp/e2e-reports/`, итог — в worker report карточки), `/audit` и `/audit-triage` (находки → BACKLOG),
  `/update-docs`.

## Что не покрыто контуром автоматически

- `make test-integration` идёт через docker compose, браузерный E2E — против хостовых `uvicorn`/`vite`.
  В воркспейсе воркера гарантированы юниты и CI. Интеграция и E2E — пункты Definition of Done, которые
  наблюдатель подтверждает по отчёту воркера или сам. Устранение: `containerized-stack` в BACKLOG.
- Аудит и post-audit E2E, раньше обязательные шаги закрытия спринта, теперь включаются в DoD явно, если
  спринту нужны.

## Коммиты

Обычное сообщение коммита без трейлеров AI-коавторства: ревью-политика пайплайна отвергает их в истории
ветки. Воркер пушит только в свой проект; кросс-репозиторные части делает PO.
