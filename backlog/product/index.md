# Product queue

Живая очередь канонического репозитория. Не lifecycle продукта.

## Брать в работу

1. [V3 qualification fix plan](v3/qualification-fix-plan.md) — исправить
   блокирующие дефекты, найденные независимой проверкой.
2. [V3 completion plan](v3/completion-plan.md) — исходный план сохранён как
   проверяемая история требований; заявленное завершение не принято.
3. [DF3-009](DF3-009.md) — после инженерной готовности выполнить девять
   реальных прогонов на reference 35B A3B Worker.

| ID | Статус | Результат |
|---|---|---|
| [V3-QF](v3/qualification-fix-plan.md) | `ready` | Устранить дефекты qualification и повторить инженерную проверку |
| [V3-COMP](v3/completion-plan.md) | `needs-correction` | Шаги 1–8 заявлены выполненными, но acceptance не подтверждён |
| [DF3-009](DF3-009.md) | `blocked` | Ожидает V3-QF, чистую квалификацию и LM Studio host |

Завершённые карточки удалены из дерева и доступны в Git history.
