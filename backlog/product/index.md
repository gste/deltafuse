# Продуктовый backlog (после A12)

Дата: 2026-09-10. Этап WK — ветка `feature/2026-09-10-worker-kernel`, пока не сказано иначе.

- **Статус:** `in-progress`.
- **Текущая карточка:** [WQ-001](WQ-001.md) ready-rail в fuse-map (транспорт доски уже в FM-001).
- **Следующая:** UI в `../fuse-map`; контракт ядра WK закрыт кроме [WK-001](WK-001.md) как карточки-split.
- **Счётчики:** всего 7; `planned` 2; `in-progress` 0; `done` 5.

Не сюда: повтор A09, analog SDD, MCP-оркестратор, auto-accept DEC.

| ID | Идея | Слой | Статус |
|---|---|---|---|
| [WK-005](WK-005.md) | LLM adapter: скиллы пишут файлы, ядро оркестрирует | `process/skills/**` | done |
| [WK-004](WK-004.md) | Human adapter: чеклист из контракта шага, тот же `check-gate` | CLI | done |
| [WQ-001](WQ-001.md) | Очередь работы: слеш-команда без id, человек и fuse-map | проекция ядра; UI позже | planned — листинг ядра в WK-003 |
| [WK-003](WK-003.md) | Контракт шага + `deltafuse next` (Change id не обязателен) | CLI / Python API | done |
| [WK-002](WK-002.md) | Evidence runner: CLI гоняет команду и пишет YAML | CLI / Python API | done |
| [WK-001](WK-001.md) | Ядро процесса отдельно от бэка исполнителя (`llm \| human \| script`) | контракт | planned — на этой ветке |
| [FM-001](FM-001.md) | Начало поддержки fuse-map: единая точка чтения артефактов продукта | CLI / Python API, read-only | done — UI в `../fuse-map` |
