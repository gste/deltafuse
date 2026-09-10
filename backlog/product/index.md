# Продуктовый backlog (после A12)

Дата: 2026-09-10. Этап WK — ветка `feature/2026-09-10-worker-kernel`, пока не сказано иначе.

- **Статус:** `in-progress`.
- **Текущая карточка:** [WQ-001](WQ-001.md) fuse-map ready-rail; транспорт колонок — [FM-001](FM-001.md).
- **Следующая:** FM-001 `deltafuse board --json`, затем UI в `../fuse-map`.
- **Счётчики:** всего 7; `planned` 3; `in-progress` 0; `done` 4.

Не сюда: повтор A09, analog SDD, MCP-оркестратор, auto-accept DEC.

| ID | Идея | Слой | Статус |
|---|---|---|---|
| [WK-005](WK-005.md) | LLM adapter: скиллы пишут файлы, ядро оркестрирует | `process/skills/**` | done |
| [WK-004](WK-004.md) | Human adapter: чеклист из контракта шага, тот же `check-gate` | CLI | done |
| [WQ-001](WQ-001.md) | Очередь работы: слеш-команда без id, человек и fuse-map | проекция ядра; UI позже | planned |
| [WK-003](WK-003.md) | Контракт шага + `deltafuse next` (Change id не обязателен) | CLI / Python API | done |
| [WK-002](WK-002.md) | Evidence runner: CLI гоняет команду и пишет YAML | CLI / Python API | done |
| [WK-001](WK-001.md) | Ядро процесса отдельно от бэка исполнителя (`llm \| human \| script`) | контракт | planned — на этой ветке |
| [FM-001](FM-001.md) | Начало поддержки fuse-map: единая точка чтения артефактов продукта | CLI / Python API, read-only | planned — UI в `../fuse-map` |
