# Матрица согласованности контрактов и контекстных ограничений DeltaFuse

Этот документ фиксирует сопоставление проектных контрактов жизненного цикла DeltaFuse, разделяя уровни **декларации** (документация, спецификации, скиллы), **структурной проверки** (схемы JSON Schema, frontmatter шаблонов) и **runtime enforcement** (проверки FSM, гейты, CLI-валидаторы), согласно [плану анализа](../analysis-plan.md) (пакет A02).

---

## 1. Матрица контекстных контрактов и бюджетов по фазам жизненного цикла

| Фаза / Шаг | Декларируемый Read Scope (`docs/context-model.md`, `docs/workflow.md`) | Декларируемый Write Scope (`docs/workflow.md`) | Структурный контракт (JSON Schema / Frontmatter) | Runtime Enforcement (`src/deltafuse/core/context.py`, `fsm.py`, CLI) | Статус контроля | Выявленные разрывы и контрпримеры |
|---|---|---|---|---|---|---|
| **1. Intake** | Raw input, issue description, error logs, user comments. **Forbidden:** `docs/spec/**`, repository source code. | `request.md`, `change.yaml` (`status: normalized`). | `change.schema.yaml` проверяет статус `normalized`. Шаблоны `intake` не имеют schema для сырого входа. | `PHASE_CONTRACTS["intake"]` (`allowed_read: ["docs/intake/**", "docs/changes/**"]`) **не вызывается** в `fsm.py` или CLI. Запрет чтения `docs/spec/**` не форсится. | **Декларация** (структурная валидация только для `change.yaml`; runtime enforcement чтений отсутствует). | Контрпример 1: агент при нормализации может прочитать `docs/spec/**` и код, FSM `check-gate` не обнаружит нарушения. |
| **2. Route & Analyze** | `request.md`, `_capabilities.yaml`, targeted spec modules for selected slice, accepted decisions. **Forbidden:** Entire codebase, unrelated spec modules. | `routing.yaml`, `analysis.md`, `slices/SLICE-NN.md`, `coverage.yaml`, `change.yaml`. | `routing.schema.yaml`, `slice.schema.yaml` (`context_budget` опционален), `coverage.schema.yaml`. | `fsm.py` проверяет `validate_context_budget` для каждого `slice.md`, но считает токены **только по файлам из `spec_refs`**. Чтения агента не перехватываются. | **Структурный + Частичный Runtime** (проверяется размер `spec_refs` среза; реальный prompt и чтение не контролируются). | Контрпример 2: в `PHASE_CONTRACTS["analyze"]` разрешено чтение всей `docs/spec/**`, что противоречит требованию читать только целевые модули среза. |
| **3. Specify** | `request.md`, `analysis.md`, `slices/SLICE-NN.md`, target spec module, accepted decisions. **Forbidden:** Product source code. | `spec-delta.md`, updated `docs/spec/**`, `change.yaml`. | `spec-delta.schema.yaml` (frontmatter: change, slice, operation). | FSM проверяет валидность `spec-delta.md` схемой и якоря `#REQ-*`. Проверка отсутствия чтения исходного кода в runtime отсутствует. | **Структурный** (runtime enforcement запрета чтения кода отсутствует). | Контрпример 3: агент может подсмотреть существующий код реализации при составлении `spec-delta`, нарушая принцип «spec — закон, а не слепок кода». |
| **4. Decompose** | Updated spec modules, slice definition, target test suite paths. **Forbidden:** Full codebase. | `tasks/TASK-NNN-*.md`, `coverage.yaml`, `change.yaml`. | `task.schema.yaml` (требует `allowed_paths`, `forbidden_paths`, `spec_refs`). **Поле `context_budget` в схеме отсутствует!** | `fsm.py` проверяет валидность задач схемой и топологическую сортировку DAG по `depends_on`. Бюджеты токенов/файлов для задач **не вычисляются**. | **Структурный + DAG Runtime** (контролируется ацикличность графа задач; контекстные бюджеты задач не проверяются). | Контрпример 4: задача может ссылаться на 50 файлов в `spec_refs` и `allowed_paths`, превышая контекст, но FSM пропустит её без ошибок. |
| **5. Target** | Single `TASK-NNN.md`, test suite file, public API signatures of target module. **Forbidden:** Implementation code under test. | Target test file in `tests/**`, `evidence/red/<task-id>.yaml`, `change.yaml`. | `evidence.schema.yaml` (`phase: red`, `failure_category: behavioral-mismatch`, `exit_code != 0`). | `fsm.py` проверяет T1 (нет green в red), T2 (`exit_code != 0`, `result != passed`), T4 (валидность task ref). Запрет чтения кода реализации не форсится. | **Семантический Runtime для Evidence** (жесткий контроль Red-свидетельства; изоляция чтения не контролируется). | Контрпример 5: агент может прочитать `src/identity/auth.py` при написании теста, нарушая принцип Black-box Target, FSM не имеет механизма аудита чтений. |
| **6. Implement** | Single `TASK-NNN.md`, Red evidence, target test, target implementation source file. **Forbidden:** Unrelated modules and packages. | Production code in `allowed_paths`, `evidence/green/<task-id>.yaml`, `evidence/regression/<task-id>.yaml`. | `evidence.schema.yaml` (`phase: green/regression`, `exit_code: 0`, `result: passed`). | `fsm.py` проверяет статус `implemented`, наличие валидных green/regression evidence. Проверка соблюдения `allowed_paths` из метаданных задачи в FSM **отсутствует**! | **Семантический Runtime для Evidence** (проверка exit code тестов; соблюдение `allowed_paths` кодом в FSM не проверяется). | Контрпример 6: агент изменяет файл вне `allowed_paths`, `fsm.py check-gate` не сверяет git diff с `allowed_paths` задачи и успешно рапортует успех. |
| **7. Verify & Archive** | `change.yaml`, `request.md`, `routing.yaml`, `slices/**`, `tasks/**`, `coverage.yaml`, test results. **Forbidden:** Arbitrary code refactoring. | `verification.md`, `evidence/verification/run.yaml`, перемещение каталога в `docs/archive/changes/`. | `evidence.schema.yaml` (`phase: verification`, `task: null`), проверка `converged`. | `fsm.py` проверяет T3 (все задачи завершены), T8 (защита от повторной архивации). `deltafuse archive` атомарно переносит каталог. | **Полный Runtime Enforcement** (контроль статусов задач, ссылочной целостности, блокировка повторного архива). | Замечание: проверка покрытия требований `CR-*` выполняется структурно через `coverage.yaml`, но сверка с реальными тестами полагается на отчёт агента. |

---

## 2. Ключевые архитектурные разрывы (Identified Gaps)

### Gap 1: Отсутствие runtime enforcement для `PHASE_CONTRACTS`
Константа `PHASE_CONTRACTS` в `src/deltafuse/core/context.py` определяет диапазоны чтения (`allowed_read`) и записи (`allowed_write`) для всех 7 фаз, но:
- Ни в `src/deltafuse/core/fsm.py`, ни в `src/deltafuse/cli.py` эта структура **никогда не используется**;
- Проверка реального доступа агента к файловой системе не осуществляется (отсутствует перехватчик файловых операций, песочница или аудит access-логов);
- Все ограничения на чтение в `docs/context-model.md` («Forbidden Read Scope») являются **чисто декларативными инструкциями для промпта агента**.

### Gap 2: Отсутствие проверки контекстных бюджетов для фаз Target и Implement
- В `docs/context-model.md` заявлено: *«Each task executes within a strictly bounded Context Budget (max_tokens: 16000, max_files: 24)»*.
- В `process/schemas/task.schema.yaml` поле `context_budget` **вообще не предусмотрено**.
- В `src/deltafuse/core/fsm.py` вызов `validate_context_budget` происходит только для файлов в каталоге `slices/` (строка 217). В блоке валидации `tasks/` (строки 223–263) проверка контекстного бюджета полностью отсутствует.
- **Следствие:** именно на фазах Target и Implement, где агент загружает большие файлы тестов и исходного кода, риск переполнения контекста локальной модели максимален, однако автоматизированный контроль отсутствует.

### Gap 3: Усечённая оценка токенов в `validate_context_budget`
- Функция `validate_context_budget` оценивает размер только файлов из `spec_refs` среза;
- Полностью игнорируются:
  1. Текст системного промпта и инструкции навыка (`SKILL.md`);
  2. Текст самого артефакта (`SLICE-NN.md` или `TASK-NNN.md`);
  3. Содержимое файлов контекста задачи (`request.md`, `routing.yaml`);
  4. Код тестов и исходных модулей;
  5. История сообщений диалога;
  6. Резерв токенов на генерацию ответа (`reserved_output_tokens: 2000`).
- Эвристика `1 word ≈ 1.3 tokens` систематически занижает оценку токенов для исходного кода на Python/C/Rust и для кириллических текстов BPE-токенизатора локальных моделей (например, `ornith` / Qwen 2.5).

### Gap 4: Отсутствие контроля `allowed_paths` в FSM Gate
- Метаданные задачи `TASK-NNN.md` содержат обязательные поля `allowed_paths` и `forbidden_paths` (проверяются `task.schema.yaml`).
- Однако при прохождении гейта фазы Implement (`fsm.py :: validate_change_package`) **фактический git diff или список изменённых файлов не сопоставляется** с `allowed_paths` задачи. Нарушение границ задачи (`CODE-002`) runtime-гейтом FSM не отлавливается.

---

## 3. Вывод для пакета A03 (Ограничение контекста и локальный профиль)

Матрица подтверждает, что текущая кодовая база DeltaFuse реализует:
1. **Декларативный уровень:** полное и детальное описание контрактов в `docs/context-model.md` и `docs/roles.md`.
2. **Структурный уровень:** валидация схем для `slices` (`context_budget`) и `tasks` (`allowed_paths`).
3. **Runtime уровень:** частичная валидация `spec_refs` слайсов через эвристику слов в `fsm.py` и команду `deltafuse lint-context`. Контроль чтений, бюджетов задач и границ diff на уровне Python-движка отсутствует.

Данного анализа достаточно для перехода к экспериментальным измерениям токенизатора, фактического промпта и аппаратных профилей в пакете **A03**.
