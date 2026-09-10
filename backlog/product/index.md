# Продуктовый backlog (после A12)

Дата: 2026-09-10. Этап WK — ветка `feature/2026-09-10-worker-kernel`, пока не сказано иначе.

- **Статус:** `in-progress`.
- **Текущая карточка:** [WQ-001](WQ-001.md) ready-rail в fuse-map (не этот репозиторий).
- **Следующая:** UI в `../fuse-map`. Coverage не invent / Specify F-010 по срезу — отдельные карточки.
- **Счётчики:** всего 8; `planned` 1; `in-progress` 0; `done` 7.

Не сюда: повтор A09, analog SDD, MCP-оркестратор, auto-accept DEC.

| ID | Идея | Слой | Статус |
|---|---|---|---|
| [AN-001](AN-001.md) | Analyze: `next` один pass; `analyzed` = срез на каждую routing capability | CLI / гейт / skill | done |
| [WK-005](WK-005.md) | LLM adapter: скиллы пишут файлы, ядро оркестрирует | `process/skills/**` | done |
| [WK-004](WK-004.md) | Human adapter: чеклист из контракта шага, тот же `check-gate` | CLI | done |
| [WQ-001](WQ-001.md) | Очередь работы: слеш-команда без id, человек и fuse-map | проекция ядра; UI позже | planned — листинг ядра в WK-003 |
| [WK-003](WK-003.md) | Контракт шага + `deltafuse next` (Change id не обязателен) | CLI / Python API | done |
| [WK-002](WK-002.md) | Evidence runner: CLI гоняет команду и пишет YAML | CLI / Python API | done |
| [WK-001](WK-001.md) | Ядро отдельно от воркера (`Core` / `Worker`); Процесс = lifecycle | контракт + канон | done |
| [FM-001](FM-001.md) | Начало поддержки fuse-map: единая точка чтения артефактов продукта | CLI / Python API, read-only | done — UI в `../fuse-map` |
