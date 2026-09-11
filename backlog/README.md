# Backlog

Очередь работ вокруг канонического репозитория DeltaFuse. Это не lifecycle продукта и не замена `docs/**`.

Тезис текущей программы: [product/leash.md](product/leash.md).

Брать в работу:

| ID | Статус | Слой |
|---|---|---|
| [LS-001](product/LS-001.md) | `done` | `next --json` write envelope |
| [LS-002](product/LS-002.md) | `done` | `deltafuse leash` |
| [LS-003](product/LS-003.md) | `done` | orphan-diff без Change |
| [LS-004](product/LS-004.md) | `done` | hook/CI + `workflow.leash` |
| [LS-005](product/LS-005.md) | `done` | Gate только через `decide` |
| [LS-006](product/LS-006.md) | `planned` | штамп `deltafuse evidence` |
| [LS-007](product/LS-007.md) | `planned` | контракт хоста (writes + halt) |

Сводка: [product/index.md](product/index.md).

Сделано ранее: [SK-001](product/SK-001.md), [HS-001](product/HS-001.md).

Закрытые карточки, пакеты анализа, findings, матрицы и снимки экспериментов остаются в git history.

Последний коммит с полным деревом экспериментов: `e3e1149`.

```text
git log -- backlog/
git show e3e1149:backlog/analysis/experiments/A09-01/result.md
```

Не восстанавливать `backlog/analysis/experiments/**/work/**` в рабочее дерево: Cursor индексирует вложенные `AGENTS.md` и `.cursor/skills/**` как скиллы воркспейса.
