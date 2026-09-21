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
- **Состояние** читается из данных, а не из файлов репозитория: `sprint status`,
  `task list --project dnd-simulator`, `issue list --product dnd-simulator`.

## Где что живёт с 2026-09-21

- **Состояние и «что болит»** — доска. Бэклог репозитория вынесен в issue продукта `dnd-simulator`;
  `docs/BACKLOG.md`, `docs/STATUS.md` и `docs/audit.md` удалены.
- **История, дизайн и решения** — knowledge инстанса, `state/knowledge/projects/dnd-simulator/`
  (`README.md` — точка входа, `brainstorms/` — живые дизайн-документы, `archive/` — реализованное и
  отменённое плюс снимки удалённых файлов, `decisions/` — решения, включая
  `2026-09-21-dnd-docs-migration.md`).
- **В репозитории остаются**: [VISION.md](VISION.md), [ROADMAP.md](ROADMAP.md) (только раздел
  Planned), этот файл, [e2e-playbook.md](e2e-playbook.md), [LOGGING.md](LOGGING.md),
  `ARCHITECTURE.md`, `AGENTS.md`, `CLAUDE.md`, `README.md`. `open-sprint` читает ROADMAP и VISION
  как вход.
- **Воркерам карточек запрещено** заводить в репозитории BACKLOG/STATUS-подобные файлы и
  восстанавливать удалённые. Карточка, требующая правки такого файла, — повод вернуть карточку
  наблюдателю, а не выполнить её. Находки уходят в worker report, из них PO заводит issue.
- Доменные скиллы: `/e2e` (Playwright-регресс по [e2e-playbook.md](e2e-playbook.md), отчёт в
  `/tmp/e2e-reports/`, итог — в worker report карточки), `/audit` (отчёт для PO, файлов в репозитории
  не пишет), `/update-docs`. Скиллы `go` и `audit-triage` сняты вместе со спринтовой машинерией.

## Что не покрыто контуром автоматически

- `make test-integration` идёт через docker compose, браузерный E2E — против хостовых `uvicorn`/`vite`.
  В воркспейсе воркера гарантированы юниты и CI. Интеграция и E2E — пункты Definition of Done, которые
  наблюдатель подтверждает по отчёту воркера или сам. Устранение — issue «Воспроизводимый контейнерный стек и изоляция сейвов» на доске.
- Аудит и post-audit E2E, раньше обязательные шаги закрытия спринта, теперь включаются в DoD явно, если
  спринту нужны.

## Коммиты

Обычное сообщение коммита без трейлеров AI-коавторства: ревью-политика пайплайна отвергает их в истории
ветки. Воркер пушит только в свой проект; кросс-репозиторные части делает PO.
