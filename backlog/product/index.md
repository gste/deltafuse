# Product queue

Живая очередь канонического репозитория. Не lifecycle продукта.

Брать в работу: [AU-001](AU-001.md) — полный внешний аудит. Промпт: [audit-prompt.md](audit-prompt.md).

Закрытая программа: [leash.md](leash.md) — железный поводок (envelope, `leash`, hook/CI, decide, evidence stamp, хост).

| ID | Статус | Зачем |
|---|---|---|
| [AU-001](AU-001.md) | `ready` | Внешний аудит: дефекты, слабые места, steal-sheet, roadmap |
| [LS-001](LS-001.md) | `done` | `next --json` отдаёт write envelope |
| [LS-002](LS-002.md) | `done` | `deltafuse leash` сверяет diff с envelope |
| [LS-003](LS-003.md) | `done` | Orphan-правка продукта без Change |
| [LS-004](LS-004.md) | `done` | Hook + CI, `workflow.leash` |
| [LS-005](LS-005.md) | `done` | `accepted`/`rejected` только через `decide` |
| [LS-006](LS-006.md) | `done` | Evidence без штампа ядра не закрывает гейт |
| [LS-007](LS-007.md) | `done` | Хост MUST резать writes по envelope |

Закрыто в этой ветке (не брать):

| ID | Статус | Зачем |
|---|---|---|
| [SK-001](SK-001.md) | `done` | Первый `check-gate` без YAML-налога |
| [HS-001](HS-001.md) | `done` | Контракт halt (`choices`, pack, не UI в Core) |

Закрытые WK-* / BM-* / FM-* — в git history, не в дереве.
