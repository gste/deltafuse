# Prompt: fix-bug

Job prompt: взять задачу бага из `docs/todo/<story>/bug/NN-<slug>.md` — до кода. Спека сначала, код по диффу спеки.

Как использовать: вставь core prompt из [`../agent-prompt.md`](../agent-prompt.md), затем этот файл, затем путь к файлу бага (`docs/todo/<story>/bug/NN-<slug>.md`).

В GUI агентов: вызов скилла `/fix-bug <путь-к-файлу-бага>`.

Контракт файла, Spec delta, гейты — в `workflow.md` и `roles.md`. Новой роли нет: после human gate меняется роль сессии (Spec editor → Implementer).

---

## 0. Preconditions

- `stage: spec-first`.
- Ровно один баг на вызов.
- Вход: существующий файл в `docs/todo/<story>/bug/NN-<slug>.md` (если файла нет — сначала запусти `/report-bug` для триажа и оформления).
- В преамбуле: `kind: bug`, change type после сверки со спекой, якоря, гейты.
- Ветка кода: `bugfix/<slug>`.

## 1. Inbox Verification

1. Прочитай файл бага в `docs/todo/<story>/bug/NN-<slug>.md`.
2. Проверь заявленные поля: `Observed vs Expected`, `Spec delta`, `Definition of Done`.
3. Читать только связанные секции `docs/spec/**` (не весь спек-пак).

## 2. Spec then code

Не держать незакоммиченные спеку и код в одном дереве. Не писать код из ADR (`accepted: false`) и не писать код, пока спека `spec-patch` / `adr+spec` не в законе.

1. **Spec update (при `spec-patch` / `adr+spec`)**:
   - Обнови только якоря, заявленные в `Spec delta` файла бага.
   - Закоммить спеку отдельно: `git add docs/spec/ && git commit -m "spec(patch): update spec for bug NN"`.
2. **TDD (Red phase)**:
   - Напиши регрессионный тест, указанный в DoD файла задачи.
   - Запусти тест — он **обязан упасть** на текущем коде. Если уже зелёный — остановись.
3. **Implementation (Green phase)**:
   - Напиши минимальный код, делающий тест зелёным.
   - Убедись, что все тесты проходят.

## 3. PR and inbox cleanup

В том же PR:

1. удалить файл задачи из `docs/todo/<story>/bug/`;
2. убрать строку бага из таблицы в README истории;
3. дописать Closed в `docs/todo/README.md` и пункт в `CHANGELOG.md` → `## Unreleased` (`- NN краткое описание`);
4. если задач в `task/` и `bug/` этой истории не осталось — удалить директорию `docs/todo/<story>/` и убрать историю из `## Open Stories`.

Мердж делает человек.

## 4. Definition of Done

- [ ] для `adr+spec`: код только после `accepted` и зеркала в спеке
- [ ] для `spec-patch` / `adr+spec`: `git diff -- docs/spec/` ⊂ объявленной дельты; changelog-лент в спеке нет
- [ ] регрессионный тест упал до фикса и проходит после фикса
- [ ] секретов нет в коде, тестах и логах
- [ ] файл бага удалён в этом PR; Closed в `docs/todo/README.md` и Unreleased в `CHANGELOG.md` дополнены
- [ ] если `docs/spec/**` не менялся — в ответе явно `spec unchanged`
- [ ] в default branch ничего не смерджено

В конце ответа по-русски: что сделано, чем подтверждено, какой гейт у человека. Если `docs/spec/**` не менялся — отдельной фразой `spec unchanged`.