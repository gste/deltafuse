# Prompt: init-to-spec

Job prompt: собрать модульный пакет спецификации в `docs/spec/` и черновики ADR в `docs/decisions/` из входящих требований в `docs/inbox/**`.

Как использовать: вставь core prompt из [`../agent-prompt.md`](../agent-prompt.md), затем этот файл, затем укажи `docs/inbox/**`.

В GUI агентов: вызов скилла `/init-to-spec`.

---

## 0. Preconditions

- `stage: bootstrap`.
- Роль: **Spec editor (draft)**.
- `docs/inbox/` существует и содержит сырые требования (или указан конкретный файл).
- Смысл берётся только из `docs/inbox/**` и принятых решений.

## 1. Processing and Spec Pack Assembly

1. Изучи все файлы в `docs/inbox/`.
2. Выдели архитектурные развилки в черновики ADR: `docs/decisions/NNNN-<slug>.md` (`status: proposed`, `accepted: false`).
3. Собери модульный пакет спецификации:
   - `docs/spec/README.md` — оглавление, Tour, Acceptance checklist, Coverage matrix.
   - `docs/spec/00-context.md` — границы, акторы, human-gated зоны.
   - `docs/spec/01-*.md`..`NN-*.md` — функциональные модули в императивном стиле.
4. **Важно**: ни одной ссылки на `docs/inbox/**` внутри `docs/spec/**` (спецификация самодостаточна).
5. Перемести обработанные файлы из `docs/inbox/` в `docs/archive/inbox/`.

## 2. Definition of Done

- [ ] Создан `docs/spec/README.md` с оглавлением и таблицей покрытия
- [ ] Модули спеки написаны в императивном стиле с постоянными якорями
- [ ] Архитектурные развилки оформлены в `docs/decisions/` со статусом `accepted: false`
- [ ] Обработанные файлы перемещены из `docs/inbox/` в `docs/archive/inbox/`
- [ ] Задачи в `docs/todo/` и продуктовый код не создавались
- [ ] Коммит: `git add docs/spec/ docs/decisions/ docs/inbox/ docs/archive/ && git commit -m "spec: compile modular specification pack from inbox"`

В конце ответа по-русски: структура созданного спек-пака, список черновиков ADR и приглашение человеку провести ревью через `docs/spec/README.md` или запустить `/audit-spec`.