# Product queue

Живая очередь канонического репозитория. Не lifecycle продукта.

Брать в работу: [DF3-005](DF3-005.md) — wheel/runtime bundle и безопасный upgrade.

Активная программа: [DeltaFuse 3.0](deltafuse-3.md).

Закрытая программа: [leash.md](leash.md) — железный поводок (envelope, `leash`, hook/CI, decide, evidence stamp, хост).

| ID | Статус | Зачем |
|---|---|---|
| [DF3-001](DF3-001.md) | `done` | V3 contracts и абсолютные acceptance thresholds ([v3/](v3/)) |
| [DF3-002](DF3-002.md) | `done` | Archive bypass и route convergence |
| [DF3-003](DF3-003.md) | `done` | CI leash и framework manifest |
| [DF3-004](DF3-004.md) | `done` | Core-owned lifecycle transitions |
| [DF3-005](DF3-005.md) | `ready` | Distribution, scaffolding и upgrade |
| [DF3-006](DF3-006.md) | `blocked` | Evidence и envelope authority |
| [DF3-007](DF3-007.md) | `blocked` | Human Gate receipts и integrity profiles |
| [DF3-008](DF3-008.md) | `blocked` | Schema v3 и Declare contracts |
| [DF3-009](DF3-009.md) | `blocked` | Bench, docs и release qualification |
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
| [AU-001](AU-001.md) | `done` | Аудит оценён; disposition и roadmap перенесены в DeltaFuse 3.0 |
| [SK-001](SK-001.md) | `done` | Первый `check-gate` без YAML-налога |
| [HS-001](HS-001.md) | `done` | Контракт halt (`choices`, pack, не UI в Core) |

Закрытые WK-* / BM-* / FM-* — в git history, не в дереве.
