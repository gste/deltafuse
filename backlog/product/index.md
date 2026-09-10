# Продуктовый backlog (после A12)

Дата: 2026-09-10. Этап WK — ветка `feature/2026-09-10-worker-kernel`, пока не сказано иначе.

- **Статус:** `in-progress`.
- **Текущая карточка:** [WQ-001](WQ-001.md) — ready-rail / удобство очереди сверх `deltafuse next`.
- **Следующая:** WK-004 human adapter; [FM-001](FM-001.md) колонки доски.
- **Счётчики:** всего 5; `planned` 3; `in-progress` 0; `done` 2.

Не сюда: повтор A09, analog SDD, MCP-оркестратор, auto-accept DEC.

| ID | Идея | Слой | Статус |
|---|---|---|---|
| [WQ-001](WQ-001.md) | Очередь работы: слеш-команда без id, человек и fuse-map | проекция ядра; UI позже | planned |
| [WK-003](WK-003.md) | Контракт шага + `deltafuse next` (Change id не обязателен) | CLI / Python API | done |
| [WK-002](WK-002.md) | Evidence runner: CLI гоняет команду и пишет YAML | CLI / Python API | done |
| [WK-001](WK-001.md) | Ядро процесса отдельно от бэка исполнителя (`llm \| human \| script`) | контракт | planned — на этой ветке |
| [FM-001](FM-001.md) | Начало поддержки fuse-map: единая точка чтения артефактов продукта | CLI / Python API, read-only | planned — UI в `../fuse-map` |
