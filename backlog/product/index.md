# Product queue

Живая очередь канонического репозитория. Не lifecycle продукта.

## Брать в работу

1. [V3 qualification fix plan, wave 2](v3/qualification-fix-plan-wave-2.md) —
   закрыть оставшиеся fail-open границы QF-013–QF-018.
2. [V3 qualification fix plan, wave 1](v3/qualification-fix-plan.md) —
   QF-001–QF-011 реализованы, но независимая приёмка выявила новые блокеры;
   QF-012 остаётся pending.
3. [V3 completion plan](v3/completion-plan.md) — исходный план сохранён как
   проверяемая история требований; заявленное завершение не принято.
4. [DF3-009](DF3-009.md) — после инженерной готовности выполнить девять
   реальных прогонов на reference 35B A3B Worker.

| ID | Статус | Результат |
|---|---|---|
| [V3-QF2](v3/qualification-fix-plan-wave-2.md) | `ready` | Изоляция, exact T2, fail-closed T4, crash recovery, strict artifacts |
| [V3-QF1](v3/qualification-fix-plan.md) | `implemented-needs-correction` | QF-001–QF-011 реализованы; QF-012 pending; приёмка выявила wave 2 |
| [V3-COMP](v3/completion-plan.md) | `needs-correction` | Шаги 1–8 заявлены выполненными, но acceptance не подтверждён |
| [DF3-009](DF3-009.md) | `blocked` | Ожидает V3-QF2, повторную квалификацию и LM Studio host |

Завершённые карточки удалены из дерева и доступны в Git history.
