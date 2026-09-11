# Product queue

Живая очередь канонического репозитория. Не lifecycle продукта.

Программа: [leash.md](leash.md) — железный поводок (envelope, `leash`, hook/CI, decide, evidence stamp, хост).

Брать в работу: **LS-007**.

| ID | Статус | Зачем |
|---|---|---|
| [LS-001](LS-001.md) | `done` | `next --json` отдаёт write envelope |
| [LS-002](LS-002.md) | `done` | `deltafuse leash` сверяет diff с envelope |
| [LS-003](LS-003.md) | `done` | Orphan-правка продукта без Change |
| [LS-004](LS-004.md) | `done` | Hook + CI, `workflow.leash` |
| [LS-005](LS-005.md) | `done` | `accepted`/`rejected` только через `decide` |
| [LS-006](LS-006.md) | `done` | Evidence без штампа ядра не закрывает гейт |
| [LS-007](LS-007.md) | `planned` | Хост MUST резать writes по envelope |

Закрыто в этой ветке (не брать):

| ID | Статус | Зачем |
|---|---|---|
| [SK-001](SK-001.md) | `done` | Первый `check-gate` без YAML-налога |
| [HS-001](HS-001.md) | `done` | Контракт halt (`choices`, pack, не UI в Core) |

Закрытые WK-* / BM-* / FM-* — в git history, не в дереве.
