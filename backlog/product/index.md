# Product queue

Живая очередь канонического репозитория. Не lifecycle продукта.

## Брать в работу

1. [V3 qualification fix plan, wave 3](v3/qualification-fix-plan-wave-3.md) —
   исправить command boundary, disk re-evaluation и provenance QF-019–QF-025.
2. [V3 qualification fix plan, wave 2](v3/qualification-fix-plan-wave-2.md) —
   реализован, но независимая приёмка выявила оставшиеся блокеры.
3. [V3 qualification fix plan, wave 1](v3/qualification-fix-plan.md) —
   QF-001–QF-011 реализованы, но независимая приёмка выявила новые блокеры;
   QF-012 остаётся pending.
4. [V3 completion plan](v3/completion-plan.md) — исходный план сохранён как
   проверяемая история требований; заявленное завершение не принято.
5. [DF3-009](DF3-009.md) — после инженерной готовности выполнить девять
   реальных прогонов на reference 35B A3B Worker.

| ID | Статус | Результат |
|---|---|---|
| [V3-QF3](v3/qualification-fix-plan-wave-3.md) | `ready` | Исполнимый container boundary, пересчёт T1–T8, integrity и evidence |
| [V3-QF2](v3/qualification-fix-plan-wave-2.md) | `implemented-needs-correction` | QF-013–QF-017 реализованы; QF-018 partial; открыта wave 3 |
| [V3-QF1](v3/qualification-fix-plan.md) | `implemented-needs-correction` | QF-001–QF-011 реализованы; QF-012 pending; приёмка выявила wave 2 |
| [V3-COMP](v3/completion-plan.md) | `needs-correction` | Шаги 1–8 заявлены выполненными, но acceptance не подтверждён |
| [DF3-009](DF3-009.md) | `blocked` | Ожидает V3-QF3, QF-025 и LM Studio host |

Завершённые карточки удалены из дерева и доступны в Git history.
