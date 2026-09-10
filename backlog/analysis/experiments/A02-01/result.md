# A02-01 — Сопоставить контракт ограничения контекста

**Verdict: `pass` для условий карточки (с выявлением ограничения [F-002](../../findings/F-002.md)).** На ревизии `60ea40438b0142797848356c660ab88286565e7d` (рабочий HEAD `d4c0d7b37a4e69b3506114eb9a68eebfa838e55e`) выполнено детальное сопоставление контрактов ограничения контекста, бюджетов токенов и полномочий чтения/записи по всем 7 фазам жизненного цикла (`Intake`, `Route & Analyze`, `Specify`, `Decompose`, `Target`, `Implement`, `Verify`).

Результаты сопоставления зафиксированы в нормативной матрице [backlog/matrices/contracts.md](../../../matrices/contracts.md).

## Ключевые наблюдения и сопоставление уровней контроля

| Фаза | Декларация (`context-model.md`) | Структура (Schemas/Templates) | Runtime Enforcement (`context.py`, `fsm.py`, CLI) | Наблюдаемый статус |
|---|---|---|---|---|
| **Intake** | Чтение только raw input; запрет `docs/spec/**` и кода | `change.schema.yaml` | `PHASE_CONTRACTS["intake"]` не вызывается; перехват чтений отсутствует | **Декларация** |
| **Route & Analyze** | Чтение целевых модулей среза; запрет чужих модулей | `slice.schema.yaml` (`context_budget` опционален) | `validate_context_budget` вызывается в FSM и CLI только для файлов `spec_refs` среза | **Структурный + Частичный Runtime** |
| **Specify** | Чтение среза и spec; запрет исходного кода | `spec-delta.schema.yaml` | Валидация frontmatter и якорей; запрет чтения кода в runtime не контролируется | **Структурный** |
| **Decompose** | Чтение spec и среза; запрет полной кодовой базы | `task.schema.yaml` (требует `allowed_paths`, но **нет `context_budget`**) | FSM валидирует DAG задач; бюджеты задач по токенам/файлам **не вычисляются** | **Структурный + DAG Runtime** |
| **Target** | Чтение 1 задачи, тестов, API; запрет кода реализации | `evidence.schema.yaml` (`phase: red`, T1, T2) | FSM строго проверяет T1 (нет green в red), T2 (`exit_code != 0`, `result != passed`); аудит чтений отсутствует | **Семантический Runtime для Evidence** |
| **Implement** | Чтение 1 задачи, target test/source; запрет чужих модулей | `evidence.schema.yaml` (`phase: green/regression`) | FSM проверяет green/regression evidence; проверка соблюдения `allowed_paths` кодом в FSM отсутствует | **Семантический Runtime для Evidence** |
| **Verify** | Чтение Change-пакета и тестов; запрет рефакторинга | `evidence.schema.yaml` (`phase: verification`), `converged` | FSM проверяет T3 (все задачи закрыты), T8 (иммутабельность архива); `deltafuse archive` атомарен | **Полный Runtime Enforcement** |

## Архитектурные находки и контрпримеры ([F-002](../../findings/F-002.md))

1. **`PHASE_CONTRACTS` не активен в runtime:** константа `PHASE_CONTRACTS` в `src/deltafuse/core/context.py` декларирует `allowed_read` и `allowed_write`, но нигде в `fsm.py` или CLI не вызывается. Ограничения на чтение файлов («Forbidden Read Scope») являются декларативными инструкциями для LLM-промптов.
2. **Пропуск проверки бюджетов для фаз Target и Implement:** в `task.schema.yaml` отсутствует поле `context_budget`. В `fsm.py` вызов `validate_context_budget` производится только для `slices/`, игнорируя задачи (`tasks/`), где риск переполнения контекста максимален из-за исходного кода и тестов.
3. **Усечённый расчёт токенов:** `validate_context_budget` суммирует токены только по `spec_refs`, игнорируя тело задачи/слайса, системный промпт, инструкции навыка (`SKILL.md`) и резерв ответа (2000 токенов). Эвристика `1 word ≈ 1.3 tokens` не откалибрована под кириллицу и код BPE-токенизаторов.
4. **Непроверяемость `allowed_paths` в FSM:** гейт `implemented` проверяет наличие evidence, но не сопоставляет git diff реализации с метаданными задачи `TASK-NNN.md :: allowed_paths`.

## Handoff

- **Карточка A02-01 выполнена:** создана матрица [backlog/matrices/contracts.md](../../../matrices/contracts.md), оформлен дефект/лимитация [F-002](../../findings/F-002.md).
- **Готовность к A03:** полученных данных полностью достаточно для перехода к исследованию токенизатора и профилей в пакете A03 (`A03-01` .. `A03-05`).
- **Следующая задача по очереди:** [A02-02 — Проверить контракт Intake](../../packets/A02-02.md) (исследование контракта Intake и нормализации требований).
