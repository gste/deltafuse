# Prompt: implement-task

Job prompt: реализовать **одну** задачу из `docs/todo/<story>/NN-<slug>.md` по TDD строго в соответствии со спецификацией `docs/spec/`.

Как использовать: вставь core prompt из [`../agent-prompt.md`](../agent-prompt.md), затем этот файл, затем путь к файлу задачи (`docs/todo/<story>/NN-<slug>.md`).

В GUI агентов: вызов скилла `/implement-task docs/todo/<story>/NN-<slug>.md`.

---

## 0. Preconditions

- `stage: spec-first`.
- Роль: **Implementer**.
- Вход: существующий файл задачи в `docs/todo/<story>/NN-<slug>.md` (если файла нет — запусти `/triage`).
- Ветка кода: указана в задаче (`feature/<slug>` или `bugfix/<slug>`).

## 1. Spec & TDD Execution

1. **Spec update (при `Spec delta` != `none`)**:
   - Обнови только указанные якоря в `docs/spec/**`.
   - Закоммить спеку отдельно: `git add docs/spec/ && git commit -m "spec(patch): update requirements for NN <slug>"`.
2. **TDD (Red phase)**:
   - Напиши автоматизированный тест, указанный в DoD задачи.
   - Запусти тест — он **обязан упасть** на текущем коде. Если уже зелёный — остановись.
3. **Implementation (Green phase)**:
   - Напиши минимальный чистый код, делающий тест зелёным.
   - Запусти весь набор тестов подсистемы — убедись, что нет регрессий.
   - Закоммить код: `git add src/ tests/ && git commit -m "feat/fix: implement NN <slug>"`.

## 2. Close Task & Cleanup

В том же PR:
1. Удали файл задачи `docs/todo/<story>/NN-<slug>.md`.
2. Убери строку задачи из таблицы в `docs/todo/<story>/README.md`.
3. Допиши строку в таблицу `## Closed Slices` в `docs/todo/README.md`.
4. Добавь один пункт в `CHANGELOG.md` под `## Unreleased` (`- NN краткое описание`).
5. Если в `docs/todo/<story>/` не осталось задач — удали директорию истории и убери её из `## Open Stories`.

## 3. Definition of Done

- [ ] Код и тесты строго соответствуют `docs/spec/**`
- [ ] Тест сначала упал на старом коде, затем прошёл на новом
- [ ] Нет секретов и кредов
- [ ] Файл задачи удален, `docs/todo/README.md` и `CHANGELOG.md` обновлены
- [ ] `git push` НЕ выполнялся (Human Gate)

В конце ответа по-русски: что сделано, какими тестами подтверждено, статус спеки (`spec unchanged` или дифф дельты).