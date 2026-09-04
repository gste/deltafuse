# Prompt: plan-story

Job prompt: нарезать принятую спецификацию (`stage: spec-first`) или спецификационный дифф (`git diff -- docs/spec/`) на атомарные задачи в `docs/todo/<story>/NN-<slug>.md`.

Как использовать: вставь core prompt из [`../agent-prompt.md`](../agent-prompt.md), затем этот файл, затем укажи модуль спеки или историю для планирования. В GUI агентов: вызов скилла `/plan-story`.

---

## 0. Preconditions

- `stage: spec-first`.
- Роль: **Planner**. Не пишет продуктовый код.
- Вход: принятые модули `docs/spec/**` или `git diff -- docs/spec/`.

## 1. Steps

1. **Анализ спецификации / диффа**:
   - Выдели функциональные слайсы и точные якоря спеки (`Spec delta`).
2. **Атомарная нарезка**:
   - Нарежь историю на небольшие, независимые задачи (каждая задача ~до 300 строк кода + тесты).
   - Вычисли сквозные номера `NN = 1 + max(Closed ∪ live task files)`.
   - Создай файлы задач `docs/todo/<story>/NN-<slug>.md`.
3. **Регистрация в очереди**:
   - Создай/обнови `docs/todo/<story>/README.md` с таблицей задач.
   - Добавь историю в `## Open Stories` в `docs/todo/README.md`.

## 2. Definition of Done

- [ ] Задачи нарезаны строго по спецификации с указанием якорей и DoD
- [ ] Каждая задача имеет сквозной номер `NN` и целевую ветку `feature/<slug>` или `bugfix/<slug>`
- [ ] Задачи зарегистрированы в `docs/todo/`
- [ ] Продуктовый код не тронут
- [ ] Локальный коммит: `git add docs/todo/ && git commit -m "plan(story): slice tasks for <story>"`