# Продуктовый backlog (после A12)

Дата: 2026-09-10. Этап агента — ветка `feature/2026-09-10-worker-agent`. Ядро 2.3.0 на `master`.

- **Статус:** `in-progress`.
- **Текущая карточка:** [WA-001](WA-001.md) агент-воркер + пилот S05 на ornith.
- **Следующая:** WQ-001 UI в `../fuse-map` (не этот репозиторий), после пилота.
- **Счётчики:** всего 11; `planned` 2; `in-progress` 0; `done` 9.

Не сюда: повтор A09 11/11, analog SDD, MCP-оркестратор, auto-accept DEC, LLM внутри Core.

| ID | Идея | Слой | Статус |
|---|---|---|---|
| [WA-001](WA-001.md) | Агент-воркер: песочница `next`; пилот S05 Specify | Worker `llm` | planned |
| [AN-003](AN-003.md) | Specify: `next` один срез; live spec только в `spec_refs` | CLI / гейт / skill | done — 2.3.0 |
| [AN-002](AN-002.md) | Ядро пишет `coverage.yaml` из routing и срезов | CLI / гейт / skill | done — 2.3.0 |
| [AN-001](AN-001.md) | Analyze: `next` один pass; `analyzed` = срез на каждую routing capability | CLI / гейт / skill | done — 2.3.0 |
| [WK-005](WK-005.md) | LLM adapter: скиллы пишут файлы, ядро оркестрирует | `process/skills/**` | done |
| [WK-004](WK-004.md) | Human adapter: чеклист из контракта шага, тот же `check-gate` | CLI | done |
| [WQ-001](WQ-001.md) | Очередь работы: слеш-команда без id, человек и fuse-map | проекция ядра; UI позже | planned — листинг ядра в WK-003 |
| [WK-003](WK-003.md) | Контракт шага + `deltafuse next` (Change id не обязателен) | CLI / Python API | done |
| [WK-002](WK-002.md) | Evidence runner: CLI гоняет команду и пишет YAML | CLI / Python API | done |
| [WK-001](WK-001.md) | Ядро отдельно от воркера (`Core` / `Worker`); Процесс = lifecycle | контракт + канон | done |
| [FM-001](FM-001.md) | Начало поддержки fuse-map: единая точка чтения артефактов продукта | CLI / Python API, read-only | done — UI в `../fuse-map` |
