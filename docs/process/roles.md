# Roles and permissions

Процесс делит ответственность между человеком и ИИ. Ни одна роль не объединяет «придумать требование» и «написать код под него» в одном неконтролируемом шаге.

## Summary table

| Роль | Кто выполняет | За что отвечает |
|---|---|---|
| Implementer | ИИ-агент | TDD реализация, тесты, PR по задаче (`/implement-task`) |
| Planner | ИИ-агент или человек | нарезка story и задач в `docs/todo/` (`/plan-story`) |
| Auditor | ИИ-агент | аудит спеки (`/audit-spec`), триаж входящего сырья (`/triage`) |
| Spec editor | ИИ черновит, **человек мерджит** | `docs/spec/**`, зеркалирование ADR |
| Decision owner | **человек** | `status` в `docs/decisions/**` (`accepted: true`) |
| Maintainer | **человек** | merge в default branch, релиз, `git push` |

## 4 Core Jobs & Skills

1. **`/triage` (Auditor / Intake Triage)**: Принимает любой сырой вход (из чата или `docs/inbox/`), задает уточняющие вопросы (Stop-and-Ask), сопоставляет со спекой, компилирует спеку/ADR или оформляет задачу в `docs/todo/<story>/NN-<slug>.md`. Переносит вход в `docs/archive/inbox/`. Не пишет продуктовый код.
2. **`/audit-spec` (Auditor)**: Проверяет непротиворечивость `docs/spec/`, зеркалирует принятые ADR (`accepted: true`) в закон и выявляет скрытые развилки.
3. **`/plan-story` (Planner)**: Нарезает принятую спеку или `git diff -- docs/spec/` на атомарные задачи в `docs/todo/<story>/NN-<slug>.md`.
4. **`/implement-task` (Implementer)**: Универсальное TDD исполнение любой задачи из `docs/todo/<story>/NN-<slug>.md` (падающий тест -> минимальный код -> удаление задачи -> `CHANGELOG.md`).

## AI must not

- **Выполнять `git push`** (КАТЕГОРИЧЕСКИЙ ЗАПРЕТ).
- Выполнять разрушающие команды (`git push --force`, `git reset --hard`, `git clean -f`).
- Ставить ADR `accepted: true` или `rejected`.
- Мерджить в default branch.
- Менять `docs/spec/**` или `docs/decisions/**` без задачи, которая это явно разрешает.
- Трогать якоря спеки вне объявленной Spec delta.
- Придумывать поведение продукта, которого нет в `docs/spec/`.
- Реализовывать из чата, `docs/inbox/` или текста ADR без соответствующего императива в спеке.
- Коммитить секреты и реальные креды.

## Human only

- **Выполнять `git push`** в удалённый репозиторий.
- Принимать и отклонять ADR (`accepted: true`).
- Принимать первоначальный пакет спецификации и одобрять PR в `docs/spec/`.
- Одобрять merge PR в default branch.
- Финальное слово по безопасности, кредам и границам доверия.

## RACI (compact)

| Активность | AI Implementer | AI Planner/Auditor | Человек |
|---|:---:|:---:|:---:|
| Триаж входящего сырья (`/triage`) | — | **R** | **A** |
| Черновик ADR (`docs/decisions/`) | — | **R** | **A** |
| **Принятие ADR (`accepted: true`)** | ❌ Запрещено | ❌ Запрещено | **Только человек** |
| Правка спецификации (`docs/spec/`) | **R** (черновик) | C | **A (merge)** |
| Нарезка задач истории (`/plan-story`) | C | **R** | **A** |
| Код и модульные тесты (`/implement-task`) | **R** | C | **A (ревью)** |
| Merge в main и `git push` | ❌ Запрещено | ❌ Запрещено | **Только человек** |

R = делает работу, A = утверждает / отвечает, C = консультируется.