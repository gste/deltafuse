# Product queue

Живая очередь канонического репозитория. Не lifecycle продукта.

## Брать в работу

1. [V3 completion plan](v3/completion-plan.md) — сначала устранить блокирующие
   дефекты qualification runner и Worker-контрактов.
2. [DF3-009](DF3-009.md) — после инженерной готовности выполнить девять
   реальных прогонов на reference 35B A3B Worker.

| ID | Статус | Результат |
|---|---|---|
| [V3-COMP](v3/completion-plan.md) | `ready` | Runner и измерения соответствуют T1–T8 |
| [DF3-009](DF3-009.md) | `blocked` | Release qualification; ожидает V3-COMP и LM Studio host |

Завершённые карточки удалены из дерева и доступны в Git history.
