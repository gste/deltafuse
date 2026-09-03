# Prompts directory

Процедурные промпты стандартных работ DeltaFuse. Каждый промпт задаёт алгоритм для конкретной роли и вызывается соответствующим Agent Skill.

## Catalog

| # | Файл | Роль | Основной результат | Когда запускается |
|---|---|---|---|---|
| **01** | [`01-triage.md`](./01-triage.md) | Auditor / Triage | `docs/spec/**`, `docs/decisions/**`, `docs/todo/**` | Приём и триаж любого входящего сырья (ТЗ, ревью, логи) из `docs/inbox/` или чата. |
| **02** | [`02-audit-spec.md`](./02-audit-spec.md) | Auditor / Spec editor | `docs/spec/**`, `docs/decisions/**` | Проверка непротиворечивости спеки, зеркалирование принятых ADR, актуализация матрицы покрытия. |
| **03** | [`03-plan-story.md`](./03-plan-story.md) | Planner | `docs/todo/<story>/**` | Нарезка принятой спецификации или спецификационного диффа на атомарные задачи. |
| **04** | [`04-implement-task.md`](./04-implement-task.md) | Implementer | Код, Тесты, PR | Реализация любой задачи из `docs/todo/<story>/NN-<slug>.md` по TDD. |