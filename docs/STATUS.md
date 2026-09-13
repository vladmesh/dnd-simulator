# Project Status

Состояние проекта живёт не в этом файле, а на доске секретаря. С 2026-09-12 проект переведён на общий
контур установки (issue `issue:bed4db0907e34fe7b7db` продукта `dnd-simulator`): спринт — сущность с целью
и Definition of Done, карточки режет наблюдатель, состояние читается из данных.

```bash
S=/home/dev/secretary/.venv/bin/secretary
$S sprint list --status open                 # есть ли открытый спринт, резервирующий dnd-simulator
$S sprint status --ref sprint:<ID>           # сводка: карточки, бюджет, наблюдатель
$S task list --project dnd-simulator         # карточки проекта
$S issue list --product dnd-simulator        # продуктовые issue (вход для спринтов)
```

Что где:

- Куда идём — [ROADMAP.md](ROADMAP.md), зачем — [VISION.md](VISION.md), что болит — [BACKLOG.md](BACKLOG.md).
- Как устроен процесс — [SPRINT_PIPELINE.md](SPRINT_PIPELINE.md).
- История спринтов 001-024, отчёты E2E и архив брейнштормов — knowledge инстанса секретаря,
  `state/knowledge/projects/dnd-simulator/` (README там содержит таблицу Sprint History).

Последнее состояние до переноса (2026-09-05): Sprint 024 playtest-quick-wins закрыт, активного спринта
нет, блокеров нет. Кандидаты на следующий спринт из BACKLOG: `combat-status-single-source` (зонтик над
`rest-in-combat-not-rejected` и `flee-scene-separation`), `load-combat-round-resume`, `hit-dice-short-rest`;
либо возврат к эпику simulation-core (`inner-self`).

Техническое обновление 2026-09-13: переваривание внутреннего я применяет правила для всех носителей ядра;
только `LlmBrain` поверх этого предложения вызывает свой клиент, валидирует полное ядро и дневник и при
ошибке оставляет предложение. Alignment сдвигают только правила. В decision tool call LlmBrain может
вернуть короткую мысль под session world-state gate, а prompt получает явные секции личности; чужая речь
в буфере и prompt помечена как услышанная. Отклонённый tool call передаёт следующей попытке краткую
причину, а безопасные логи фиксируют число retry и форму принятого digest. Переваривание принимает один
JSON fence и быстро возвращается к rules fallback при ограниченном timeout/retry. `make live-inner-self`
даёт ручной real-model отчёт через GM API и не входит в CI; для него нужны `OPENROUTER_API_KEY` и
`LLM_MODEL` в оболочках сервера и сценария.
