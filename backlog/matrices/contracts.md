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

---

## 4. Детальная матрица инвариантов фазы Intake (A02-02)

| Инвариант / Свойство | Документация (`docs/**`) | Навык агента (`process/skills/**`) | Схема / Шаблон (`process/**`) | FSM Runtime Gate (`core/fsm.py`) | Положительный тест (CI/Unit) | Отрицательный / Мутационный тест | Статус контроля |
|---|---|---|---|---|---|---|---|
| **INT-01: Изоляция чтения (Read Scope Isolation)** | `docs/workflow.md:32-35`, `docs/roles.md:53` (запрет чтения `docs/spec/**`, кода, задач). | `intake/SKILL.md:14-20` (Read only raw request, config, schemas; do not read spec/code/tests). | `templates/change/request.md:5` (Normalize without evaluating vs spec/code). | `PHASE_CONTRACTS["intake"]` объявлен в `context.py`, но в `fsm.py` **не проверяется**. | — (нет теста на запрет чтения) | **Отсутствует** (runtime enforcement чтений не реализован, [F-002](../findings/F-002.md)). | **Декларация** |
| **INT-02: Извлечение и стабильность claims (`CR-*`)** | `docs/workflow.md:41,48` (нумерация `CR-001..`, минимум 1 claim в `request.md`). | `intake/SKILL.md:26,31` (стабильные ID, запрет тихого переписывания claims). | `templates/change/request.md:7-10`, `schemas/change.schema.yaml:32`. | `fsm.py:182` (`extract_claims_from_request` парсит `\bCR-[0-9]{3,}\b`). | `tests/unit/test_fsm.py:49` (`check_gate("intake") == []`). | `tests/e2e/test_failure_modes.py:32` (удаление `request.md` или порча claims ломает гейт). | **Семантический Runtime** |
| **INT-03: Начальный статус FSM и целостность артефактов (T5)** | `docs/workflow.md:43`, `docs/state-machine.md:15,58` (`status: normalized`). | `intake/SKILL.md:25` (создание `change.yaml` со `status: normalized`). | `schemas/change.schema.yaml:16` (`enum: [normalized, ...]`). | `fsm.py:146-149` (T5: статус `normalized` запрещает наличие `tasks/` или `evidence/`). | `tests/unit/test_fsm.py:27-51` (успешный проход гейта с чистым пакетом). | `tests/unit/test_fsm_mutations.py:136` (`test_t5_status_artifacts_mismatch` — ошибка при наличии tasks в normalized). | **Полный Runtime Enforcement** |
| **INT-04: Допустимые переходы из `normalized`** | `docs/state-machine.md:41,58` (допустимы: `analyzing`, `rejected`, `duplicate`). | `intake/SKILL.md:37` (рекомендация перехода к `/analyze-change`). | `schemas/change.schema.yaml:16`. | `fsm.py:41` (`ALLOWED_CHANGE_TRANSITIONS["normalized"] = {"analyzing", "rejected", "duplicate"}`). | `tests/unit/test_fsm.py:59` (`can_transition("normalized", "analyzing") is True`). | `tests/unit/test_fsm.py:81` (`can_transition("normalized", "converged") is False`). | **Полный Runtime Enforcement** |
| **INT-05: Валидация схемы пакета Change** | `docs/workflow.md:47` (`change.yaml` passes `change.schema.yaml`). | `intake/SKILL.md:25` (запись `version`, `content_hash`, `source`). | `schemas/change.schema.yaml` (strict: `additionalProperties: false`, 10 обязательных полей). | `fsm.py:114` (`registry.validate("change", change_data)`). | `tests/unit/test_schemas.py` (self-validation шаблонов и схем). | `tests/unit/test_schemas.py` (подача лишних полей или битых типов вызывает `ValidationError`). | **Структурный Runtime** |
| **INT-06: Архивация источника Intake (Provenance Archival)** | `docs/workflow.md:281-282` (перенос в `docs/archive/intake/`). | `intake/SKILL.md:29` (сохранение hash и перемещение в архив). | `schemas/change.schema.yaml:33` (`source.intake_refs`). | Ручной/skill шаг, в FSM гейте `intake` перенос не форсируется. | `tests/e2e/test_golden_workflow.py` (сквозной перенос в архив). | — | **Процедурный (Skill level)** |

### Выводы по фазе Intake (A02-02)

1. **Гарантии FSM работают надёжно:** структурная схема `change.schema.yaml`, семантическая мутация T5 (статус `normalized` не может содержать задачи или evidence) и таблица допустимых переходов (`can_transition`) полностью покрыты юнит- и мутационными тестами.
2. **Семантика Red/Green:** на фазе Intake тесты не исполняются и код не пишется. Red и Green здесь не являются lifecycle-шагами (согласно мандату AGENTS.md), а возникают позже как доказательные состояния (`evidence states`) фаз Target и Implement.
3. **Разрыв контроля чтения (INT-01):** запрет чтения документации спецификаций и кода (`docs/spec/**`, `src/**`) во время нормализации запроса остаётся исключительно инструкцией для LLM-агента (`SKILL.md`) и не контролируется FSM-валидатором на уровне файловой системы.

---

## 5. Детальная матрица инвариантов фазы Route and Analyze (A02-03)

| Инвариант / Свойство | Документация (`docs/**`) | Навык агента (`process/skills/**`) | Схема / Шаблон (`process/**`) | FSM Runtime Gate (`core/fsm.py`) | Положительный тест (CI/Unit) | Отрицательный / Мутационный тест | Статус контроля |
|---|---|---|---|---|---|---|---|
| **ANA-01: Полное покрытие claims (Claim Coverage & No Orphans)** | `docs/workflow.md:60,80`, `docs/context-model.md:136` (каждый `CR-*` обязан иметь primary capability и срез). | `analyze-change/SKILL.md:20` (назначение capability каждому claim в routing.yaml). | `routing.schema.yaml`, `coverage.schema.yaml` (структура claims). | `fsm.py:183` + `integrity.py:100` (`validate_coverage_completeness`: взаимно-однозначное покрытие claims). | `tests/unit/test_integrity.py:10` (`test_validate_coverage_completeness`). | `tests/e2e/test_failure_modes.py:32` (потеря claim или появление orphan claim ломает гейт). | **Полный Runtime Enforcement** |
| **ANA-02: Блокировка на решениях человека (Human Decision Gate)** | `docs/workflow.md:86,90,98`, `docs/roles.md:37-45,70` (агенту запрещено утверждать `DEC-*`; `proposed` блокирует `analyzed`). | `analyze-change/SKILL.md:25` (создание `DEC-*` в `status: proposed`, запрет самовольного акцепта). | `decision.schema.yaml` (`status: [proposed, accepted, rejected, superseded]`). | `fsm.py:400` (`find_unresolved_decisions_for_change`: наличие `proposed` решений возвращает `blocked-on-decision`). | `tests/unit/test_fsm.py:87` (`test_decision_blocking_gate` — `accepted` разблокирует гейт). | `tests/unit/test_fsm.py:126` (`test_decision_blocking_gate` — наличие `proposed` блокирует переход в `analyzed`). | **Полный Runtime Enforcement** |
| **ANA-03: Обязательность дельт и срезов (Typed Deltas & Slices)** | `docs/workflow.md:70-78` (7 проекций дельты), `docs/workflow.md:82-87` (инварианты операций). | `analyze-change/SKILL.md:21,24` (создание `SLICE-NN.md`, вычисление `DELTA-NN`). | `slice.schema.yaml`, `change.schema.yaml:73-88` (`$defs/delta` со всеми 7 проекциями). | `fsm.py:394` (требует непустой каталог `slices/`, валидацию всех слайсов схемой и `change.yaml`). | `tests/unit/test_schemas.py` (self-validation схемы `slice` и `change`). | `tests/unit/test_schemas.py` (нарушение типов дельт или отсутствие обязательных проекций бракуется). | **Структурный Runtime** |
| **ANA-04: Контроль контекстного бюджета слайса (`context_budget`)** | `docs/context-model.md:147`, `docs/workflow.md:68` (`max_tokens: 16000`, `max_files: 24`). | `analyze-change/SKILL.md:14,29` (разбиение срезов при превышении лимитов). | `slice.schema.yaml:45-52` (`context_budget` опционален в схеме). | `fsm.py:217` (`validate_context_budget(context_budget, ref_files)` по `spec_refs`), `deltafuse lint-context`. | `tests/unit/test_context.py:40` (`test_validate_context_budget_ok`). | `tests/unit/test_context.py:48` (`test_validate_context_budget_exceeded` — превышение лимита токенов/файлов). | **Частичный Runtime (по spec_refs)** |
| **ANA-05: Допустимые переходы FSM из `analyzing` и `analyzed`** | `docs/state-machine.md:41-44,58-60` (поддержка прямых, рекурсивных и терминальных ветвей). | `analyze-change/SKILL.md:35` (рекомендация перехода к `/specify-change`). | `change.schema.yaml:16`. | `fsm.py:42-44` (строгие множества допустимых переходов в `ALLOWED_CHANGE_TRANSITIONS`). | `tests/unit/test_fsm.py:53-79` (проверка прямых и терминальных переходов). | `tests/unit/test_fsm.py:80-85` (запрет прямых перескоков в `converged` или возврата из `rejected`). | **Полный Runtime Enforcement** |
| **ANA-06: Проверка существования capabilities каталога** | `docs/context-model.md:36-105` (`_capabilities.yaml` — нормативный источник для routing). | `analyze-change/SKILL.md:14,20` (маршрутизация только по известным возможностям). | `routing.schema.yaml:20` (`primary_capability: string`). | **Отсутствует:** FSM проверяет только синтаксис строки, но не сверяет имя с `_capabilities.yaml`. | — | — (отрицательный тест отсутствует; несуществующий capability id не блокируется). | **Декларация (Разрыв контроля)** |

### Выводы по фазе Route and Analyze (A02-03)

1. **Ключевые инварианты надёжно защищены FSM:**
   - `ANA-01` (двунаправленное покрытие claims <-> coverage без orphan claims) имеет жёсткий семантический контроль через `integrity.py`.
   - `ANA-02` (блокировка `blocked-on-decision` при наличии решений человека в статусе `proposed`) математически доказана и валидируется на каждом прогоне CI.
2. **Семантика Red/Green:** В фазе Route and Analyze тесты Target ещё не созданы, Red/Green-статусы отсутствуют; дельты по тестам и реализации фиксируются проекциями `tests.operation` и `implementation.operation` на аналитическом уровне.
3. **Обнаруженный разрыв (ANA-06):** Отсутствует валидация ссылок `primary_capability` из `routing.yaml` на фактический каталог `docs/spec/_capabilities.yaml`. Ошибочное или вымышленное имя capability в `routing.yaml` не вызывает ошибку валидации FSM.

---

## 6. Детальная матрица инвариантов фазы Specify (A02-04)

| Инвариант / Свойство | Документация (`docs/**`) | Навык агента (`process/skills/**`) | Схема / Шаблон (`process/**`) | FSM Runtime Gate (`core/fsm.py`) | Положительный тест (CI/Unit) | Отрицательный / Мутационный тест | Статус контроля |
|---|---|---|---|---|---|---|---|
| **SPC-01: Валидация дельты и якорей требований (T7)** | `docs/workflow.md:121-124`, `docs/workflow.md:127` (оформление `spec-delta.md`, обязательность существующих якорей). | `specify-change/SKILL.md:18` (bounded spec-delta with stable requirement IDs). | `spec-delta.schema.yaml`, `templates/change/spec-delta.md`. | `fsm.py:270-280` (`registry.validate("spec-delta")`, `validate_spec_ref` для `added`/`modified`). | `tests/unit/test_integrity.py:42` (`test_validate_spec_ref_success`). | `tests/unit/test_fsm_mutations.py:162` (`test_t7_broken_spec_anchor_fails` — битая ссылка `#REQ-*` бракуется). | **Полный Runtime Enforcement** |
| **SPC-02: Человеческий контроль спецификации (Human Gate: Spec)** | `docs/workflow.md:128-129`, `docs/roles.md:37-45,71-72` (AI запрещено утверждать `docs/spec/`, только Maintainer). | `specify-change/SKILL.md:23` (подача правок на Human Gate; запрет самовольного утверждения). | `spec-delta.schema.yaml:12` (`status: [proposed, accepted, rejected, superseded]`). | `fsm.py:407` (наличие `spec-delta.md` обязательно в гейте `specified`). | `tests/unit/test_fsm.py:63-65` (переход `analyzed -> specification-proposed -> specified`). | — | **Процедурный + FSM Gate** |
| **SPC-03: Отражение решений человека (Decision Mirroring)** | `docs/workflow.md:86-87`, `docs/roles.md:55` (перенос всех `DEC-* accepted` в нормативный текст `docs/spec/**`). | `specify-change/SKILL.md:21` (mirroring каждого принятого решения в spec). | `decision.schema.yaml`. | `fsm.py:409-415` (`find_unresolved_decisions_for_change`: решения в `proposed` блокируют гейт `specified`). | `tests/unit/test_fsm.py:87` (`test_decision_blocking_gate`). | `tests/unit/test_fsm.py:126` (неразрешённое решение блокирует гейт `specified`). | **Полный Runtime Enforcement** |
| **SPC-04: Единственность источника истины (SSOT, N10 Guard)** | `docs/workflow.md:114`, `docs/roles.md:11` (`docs/spec/**` — единственный закон реализации). | `specify-change/SKILL.md:29` (требования не остаются только в тикетах или коде). | `templates/change/spec-delta.md:14` (accepted `docs/spec/**` remains normative). | `fsm.py:275` (N10: ошибка при отсутствии каталога `docs/spec` при ссылках на требования). | `tests/unit/test_templates.py` (self-validation шаблона). | `tests/unit/test_fsm_mutations.py:185` (`test_n10_missing_spec_dir_fails`). | **Полный Runtime Enforcement** |
| **SPC-05: Изоляция чтения от исходного кода** | `docs/workflow.md:118`, `docs/context-model.md:148` (запрет чтения `src/**`). | `specify-change/SKILL.md:14-16` (Do not read the codebase). | `templates/change/spec-delta.md`. | `PHASE_CONTRACTS["specify"]` объявлен в `context.py`, но перехват чтений в FSM отсутствует. | — | — (отрицательный тест отсутствует, [F-002](../findings/F-002.md)). | **Декларация** |
| **SPC-06: Проверка статуса spec-delta в гейте specified** | `docs/workflow.md:129`, `docs/state-machine.md:22` (переход в `specified` после human approval). | `specify-change/SKILL.md:23`. | `spec-delta.schema.yaml:12` (`status: enum`). | **Отсутствует:** `fsm.py:407` проверяет только наличие файла, но не проверяет `meta.status == "accepted"`. | — | — (пакет с `spec-delta.md status: proposed` проходит гейт `specified`). | **Декларация (Разрыв контроля)** |

### Выводы по фазе Specify (A02-04)

1. **Строгий контроль ссылочной целостности (SPC-01, SPC-04):** FSM на 100% блокирует любые битые якоря `#REQ-*` в дельтах (мутационный тест T7) и отсутствие корня спецификаций (инвариант N10).
2. **Семантика Red/Green:** На фазе Specify утверждается нормативное требование. Статусы Red и Green здесь не используются: написание падающего Red-теста начнётся строго после декомпозиции на этапе Target.
3. **Обнаруженный разрыв (SPC-06):** В гейте `check_gate(..., "specified")` в `fsm.py` проверяется только наличие файла `spec-delta.md`, но не валидируется значение поля `status` во frontmatter (например, что оно переведено человеком из `proposed` в `accepted`). Это позволяет обойти Human Gate простой подменой статуса Change.
