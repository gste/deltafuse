# Prompt: plan-spec-patch

Job prompt: **автоматическая нарезка задач по diff спецификации**. Анализирует изменения в `docs/spec/` и создаёт атомарные файлы задач в `docs/todo/<story>/task/`.

Как использовать: вставь core prompt из [`../agent-prompt.md`](../agent-prompt.md), затем этот файл. В GUI вызывается через команду `/plan-spec-patch`.

---

## 0. Preconditions

- Изменения в `docs/spec/` уже закоммичены локально (или находятся в рабочей ветке).
- Роль на сессию: **Planner**. Продуктовый код не пишешь, спеку не меняешь.
- В преамбуле указывай `change type: spec-patch (task planning)`.

## 1. Diff Analysis Procedure

1. **Получить diff спеки:**
   ```bash
   git diff HEAD~1 -- docs/spec/
   # или относительно base ветки:
   git diff origin/main...HEAD -- docs/spec/
   ```
2. **Извлечь Spec delta:**
   - Найти все изменённые файлы (`0X-module.md`) и конкретные заголовки/якоря (`#anchor`).
3. **Определить границы задач:**
   - Если изменение небольшое (1 якорь, 1 компонент) → ровно 1 задача.
   - Если затронуто несколько слоёв (БД, API, бизнес-логика) → нарезать по границам слоёв на атомарные задачи.

## 2. Task File Contract

Каждая задача создаётся в `docs/todo/<story-id>/task/NN-<slug>.md`:

```markdown
# Task NN: <Название задачи>

- **kind**: task
- **branch**: feature/<slug>
- **Spec delta**: docs/spec/0X-module.md#anchor

## Definition of Done
- [ ] Слой/Компонент: конкретное изменение
- [ ] Tests: точное имя теста, подтверждающего поведение из спеки
```

## 3. Inbox Registration

1. Вычисли сквозной номер `NN = 1 + max(Closed ∪ live task/bug)` из `docs/todo/README.md`.
2. Создай/обнови `docs/todo/<story-id>/README.md` с таблицей задач.
3. Добавь историю в `## Open Stories` в `docs/todo/README.md`.
4. Закоммить план: `git add docs/todo/ && git commit -m "plan: slice spec patch into tasks"`.

## 4. Definition of Done

- [ ] Все изменённые якоря из `git diff -- docs/spec/` покрыты задачами.
- [ ] Задачи атомарны (DoD содержит конкретные слои и имена тестов).
- [ ] Номера `NN` сквозные и зарегистрированы в `docs/todo/README.md`.
- [ ] План закоммичен локально (без git push).
