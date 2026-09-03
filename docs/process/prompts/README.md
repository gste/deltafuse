# Prompts directory

Процедурные промпты для стандартных работ (jobs) процесса DeltaFuse. Каждый промпт задаёт пошаговый алгоритм для конкретной роли и вызывается соответствующим Agent Skill.

## Catalog

| # | Файл | Роль | Основной результат | Когда запускается |
|---|---|---|---|---|
| **01** | [`01-init-requirements.md`](./01-init-requirements.md) | Init author (draft) | `docs/init/**` | фиксация входящих сырых требований и ограничений |
| **02** | [`02-init-to-spec.md`](./02-init-to-spec.md) | Spec editor (draft) | `docs/spec/**`, `docs/decisions/**` | `stage: bootstrap`, первичная компиляция спек-пака и черновиков ADR |
| **03** | [`03-audit-spec.md`](./03-audit-spec.md) | Auditor / Spec editor | отчёт, ADR (`accepted: false`), зеркало в `docs/spec/` | аудит спеки, проверка/зеркалирование принятых ADR, выявление скрытых развилок |
| **04** | [`04-spec-to-story.md`](./04-spec-to-story.md) | Planner | `docs/todo/<story>/**` | `stage: spec-first`, нарезка принятой спецификации на Story и атомарные задачи |
| **05** | [`05-plan-spec-patch.md`](./05-plan-spec-patch.md) | Planner | `docs/todo/<story>/task/` | нарезка задач по `git diff -- docs/spec/` (после применения `spec-patch`) |
| **06** | [`06-implement-task.md`](./06-implement-task.md) | Implementer | код, тесты, PR | `stage: spec-first`, есть файл задачи в `docs/todo/<story>/task/` |
| **07** | [`07-fix-bug.md`](./07-fix-bug.md) | Spec editor → Implementer | спека, код, PR | `stage: spec-first`, файл в `docs/todo/<story>/bug/` или запрос «почини баг» |

## Conventions

- Каждый промпт самодостаточен: он описывает вход, шаги, DoD и правила коммитов для своей работы.
- Все промпты подчиняются базовым инвариантам из [`../agent-prompt.md`](../agent-prompt.md) и правилам ролей из [`../roles.md`](../roles.md).
- В GUI агентов (Cursor, Antigravity, Claude Code) работы вызываются одноимёнными командами скиллов: `/init-requirements`, `/init-to-spec`, `/audit-spec`, `/spec-to-story`, `/plan-spec-patch`, `/implement-task`, `/fix-bug`.
