# Продуктовый backlog (после A12)

Дата: 2026-09-10. Этап WK — ветка `feature/2026-09-10-worker-kernel`, пока не сказано иначе.

- **Статус:** `in-progress`.
- **Текущая карточка:** WK-003 step contract + `next` (карточка ещё не записана).
- **Следующая:** [FM-001](FM-001.md) ортогонален ядру.
- **Счётчики:** всего 3; `planned` 2; `in-progress` 0; `done` 1.

Не сюда: повтор A09, analog SDD, MCP-оркестратор, auto-accept DEC.

| ID | Идея | Слой | Статус |
|---|---|---|---|
| [WK-002](WK-002.md) | Evidence runner: CLI гоняет команду и пишет YAML | CLI / Python API | done |
| [WK-001](WK-001.md) | Ядро процесса отдельно от бэка исполнителя (`llm \| human \| script`) | контракт | planned — на этой ветке |
| [FM-001](FM-001.md) | Начало поддержки fuse-map: единая точка чтения артефактов продукта | CLI / Python API, read-only | planned — UI в `../fuse-map` |
