# Prompt: triage

Job prompt: принять любой входящий артефакт (из чата или `docs/inbox/**`), провести интерактивный анализ с человеком (Stop-and-Ask), сопоставить со спецификацией `docs/spec/**`, обновить спеку / черновики ADR / оформить задачу в `docs/todo/<story>/NN-<slug>.md`, архивировать вход в `docs/archive/inbox/` и указать команду следующего шага (`/implement-task`).

Как использовать: вставь core prompt из [`../agent-prompt.md`](../agent-prompt.md), затем этот файл, затем сырой текст (идея, ТЗ, замечание с ревью, лог ошибки) ИЛИ путь к файлу в `docs/inbox/` (например, `docs/inbox/review-comments.md`, `docs/inbox/error.log`).

В GUI агентов: вызов скилла `/triage [путь-к-файлу-или-текст]`.

---

## 0. Preconditions

- Роль: **Auditor / Intake Triage** (при обновлении спеки — **Spec editor**). Не пишет продуктовый код и тесты.
- Вход: свободный ввод в чате ИЛИ любой файл в `docs/inbox/**`.
- Обрабатывает одно логическое изменение или пачку входящих замечаний.

## 1. Intake & Clarification (Stop-and-Ask)

1. Прочитай входящие данные из чата или файла в `docs/inbox/`.
2. Если данных недостаточно для однозначного понимания требований, шагов воспроизведения или контракта:
   - **Stop-and-Ask**: задай человеку конкретные вопросы по граничным случаям, ожидаемому формату или поведению.
   - Не додумывай скрытый бизнес-контекст.

## 2. Evaluate against Specification (docs/spec/)

Сопоставь входящие требования с действующей спецификацией:

| Ситуация | Классификация | Действие в триаже |
|---|---|---|
| Проект в `stage: bootstrap` (спеки ещё нет) | `bootstrap` | Компилирует модульный пакет `docs/spec/**` (README, context, модули) и черновики ADR `docs/decisions/`. |
| Спека требует правильного, код расходится | `trivial` (баг) | Создает задачу в `docs/todo/<story>/NN-<slug>.md` (`Spec delta: none`, `kind: bug`). |
| Спека молчит или требует изменения, решение очевидно | `spec-patch` | Определяет `Spec delta` (якоря) и создает задачу в `docs/todo/<story>/NN-<slug>.md` (`kind: task` или `kind: bug`). |
| Требуется нетривиальный архитектурный выбор | `adr+spec` | Оформляет черновик ADR `docs/decisions/NNNN-<slug>.md` (`accepted: false`). Ждёт приёмки человеком. |
| Поведение уже прямо закреплено в спеке (или out-of-scope) | **Отклонено** | Стоп. Объясни человеку, почему поведение соответствует спеке, задачу не создавай. |

## 3. Create Atomic Task

Если по итогам триажа требуется реализация в коде:

1. Определи историю: `docs/todo/<story>/` (создай README истории, если его нет).
2. Вычисли следующий номер: `NN = 1 + max(Closed ∪ live task files)` из `docs/todo/README.md`.
3. Создай файл `docs/todo/<story>/NN-<slug>.md` по контракту:

```markdown
# Task NN: <Short Title>

- **kind**: task <!-- или bug -->
- **branch**: feature/<slug> <!-- или bugfix/<slug> -->
- **Spec delta**: docs/spec/0X-module.md#anchor <!-- или none -->

## Summary / Intake Reference
<Краткая суть входящего запроса или цитата замечания с ревью>

## Definition of Done
- [ ] Implementation: <конкретные изменения в коде/архитектуре>
- [ ] Tests: <название падающего теста, воспроизводящего требование или дефект>
```

4. Зарегистрируй задачу в `docs/todo/<story>/README.md` и `docs/todo/README.md`.

## 4. Archive Inbox

Если вход был из файла в `docs/inbox/`, перемести файл в `docs/archive/inbox/` (с сохранением имени или добавлением метки даты).

## 5. Definition of Done

- [ ] Входящие данные разобраны, неясности уточнены у человека
- [ ] Спецификация актуализирована (при bootstrap) или создана задача в `docs/todo/<story>/`
- [ ] Файл из `docs/inbox/` перемещен в `docs/archive/inbox/`
- [ ] Продуктовый код и тесты **не тронуты**
- [ ] Локальный коммит: `git add docs/ && git commit -m "docs(triage): process incoming intake for NN <slug>"`

В конце ответа по-русски:
- Краткий итог анализа;
- Ссылка на созданную задачу или спеку;
- **Команда следующего шага**: `/implement-task docs/todo/<story>/NN-<slug>.md`.