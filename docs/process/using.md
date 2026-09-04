# Using DeltaFuse in your repository

Как подключить процесс DeltaFuse к новому или существующему проекту.

## 1. Копирование файлов процесса

Скопируйте в корень репозитория:
- `AGENTS.md`, `CLAUDE.md`
- `.cursorrules`
- `docs/process/`
- `skills/` (в `.cursor/skills/`, `.gemini/skills/` и `.agents/skills/`)
- шаблоны из `templates/` (в `docs/todo/README.md`, `docs/decisions/` и корень `CHANGELOG.md`)

Не копировать из чужого продукта: `docs/spec/`, `docs/inbox/`, `docs/decisions/`, `docs/todo/` с чужими слайсами, исходный код.

## 2. Начальная структура

1. В `docs/process/STATUS.md` выставить `stage: bootstrap` (или `stage: spec-first`, если спека уже принята).
2. Создать пустые `docs/inbox/`, `docs/decisions/`, `docs/spec/`, `docs/todo/`, `docs/archive/inbox/`. В `docs/todo/README.md` — **Open** и пустая таблица **Closed**.

## 3. Выбор первой работы

| Ситуация | Запускаемый скилл |
|---|---|
| Продукт ещё не описан | `/init-requirements` или скиньте файл ТЗ в `docs/inbox/` |
| Есть сырые требования в `docs/inbox/`, нет `docs/spec/` | `/init-to-spec` |
| `docs/spec/` собран, нужно проверить перед приёмкой | `/audit-spec` |
| Спека принята человеком (`stage: spec-first`) | `/spec-to-story` |
| Прилетел баг, замечание с ревью или лог ошибки | `/report-bug` (ввод в чат или файл в `docs/inbox/`) |