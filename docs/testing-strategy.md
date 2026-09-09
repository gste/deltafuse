# Стратегия и архитектура тестирования DeltaFuse 2.0

> **Цель**: Модульный, детерминированный, кроссплатформенный комплекс тестов и инструментов верификации на базе **Python 3.10+ / pytest**, исключающий платформозависимые скрипты, обеспечивающий 100% контроль инвариантов спецификаций и служащий быстрым feedback-loop валидатором для инженеров и LLM-агентов.

---

## 1. Архитектурная пирамида тестирования

```text
                     ┌───────────────────────────────┐
                     │          LLM Evals            │  <- Оценка моделей & промптов
                     │   (Prompt Benchmarks / E2E)   │     (Stage 5: Schema Compliance, Gate Pass)
                     ├───────────────────────────────┤
                     │     E2E Synthetic Flows       │  <- Полный цикл Intake -> Converged -> Archive
                     │    (Deterministic Replays)    │     на синтетических фикстурах без внешних API
                     ├───────────────────────────────┤
                     │    Workflow & State Machine   │  <- FSM, гейты, DAG зависимостей,
                     │       (Process Invariants)    │     мутационные тесты T1-T8, N10, хэш-локи
                     ├───────────────────────────────┤
                     │   Schema, Layout & Contracts  │  <- Валидация 9 схем JSON Schema 2020-12,
                     │      (Structural Invariants)  │     frontmatter, шаблоны, раскладка продукта
                     └───────────────────────────────┘
```

---

## 2. Структура тестового комплекса и инструментов

Комплекс объединяет движок верификации (`src/deltafuse/`) и многоуровневый тестовый набор (`tests/`):

```text
delta-fuse/
├── src/deltafuse/                    # Ядро фреймворка, валидаторы и CLI
│   ├── __init__.py
│   ├── cli.py                        # Единая точка входа CLI (init, validate, check-gate, archive, validate-layout, lint-context, eval)
│   ├── core/
│   │   ├── archiver.py               # Неизменяемый архив: перемещение Change, проверка converged, защита от перезаписи
│   │   ├── context.py                # Upper-bound token estimate (A03-01 factors or /tokenize) and context linter
│   │   ├── frontmatter.py            # Парсер Markdown + YAML frontmatter (strict extraction)
│   │   ├── fsm.py                    # Движок состояний (18 статусов), таблица переходов и валидация гейтов
│   │   ├── graph.py                  # DAG анализатор задач: топологическая сортировка и поиск циклов
│   │   ├── hasher.py                 # Вычисление sha256 framework content hash (исключение .git, __pycache__)
│   │   ├── installer.py              # Кроссплатформенная установка, генерация адаптеров (.agents, .cursor, .gemini)
│   │   ├── integrity.py              # Ссылочная целостность: якоря #REQ-*, #SC-*, решения #DEC-*, требования CR-*
│   │   ├── layout.py                 # Валидатор эталонной раскладки продукта, lock-файлов и маркеров DO-NOT-EDIT
│   │   └── schemas.py                # Загрузчик и валидатор 9 схем JSON Schema Draft 2020-12
│   └── evals/                        # Подсистема бенчмаркинга и оценки LLM (Stage 5)
│       ├── dataset.py                # Загрузчик датасета и валидация схемы бенчмарков
│       ├── default_cases.yaml        # Базовый набор синтетических сценариев
│       ├── metrics.py                # Расчёт Schema Compliance, Gate Pass, Routing Accuracy, Claim F1
│       ├── providers.py              # Провайдеры: MockLLMProvider (детерминированный CI) и RealLLMProvider (API)
│       ├── reporter.py               # Экспорт отчётов (text, json, markdown)
│       └── runner.py                 # Движок выполнения и сбора метрик бенчмарков
├── tests/
│   ├── conftest.py                   # Общие pytest фикстуры (repo_root)
│   ├── fixtures/
│   │   └── change_builder.py         # Fluent builder (MockChangeBuilder) для синтетической сборки Change-пакетов
│   ├── unit/                         # Модульные тесты инвариантов
│   │   ├── test_schemas.py           # Валидация 9 схем JSON Schema 2020-12 и strict-режима
│   │   ├── test_templates.py         # Self-validation всех шаблонов process/templates
│   │   ├── test_frontmatter.py       # Парсинг YAML frontmatter в markdown
│   │   ├── test_graph.py             # Топологическая сортировка и цикл-детектор в задачах
│   │   ├── test_integrity.py         # Спецификационные якоря #REQ-* и решения #DEC-*
│   │   ├── test_fsm.py               # 18 канонических статусов, допустимые переходы, гейты
│   │   ├── test_fsm_mutations.py     # Семантические мутационные тесты (T1-T8, N10, lock-хэш)
│   │   ├── test_hasher.py            # Чувствительность sha256 content_hash к изменениям дистрибутива
│   │   └── test_context.py           # Контекстные бюджеты и фазовые контракты
│   ├── integration/                  # Интеграционные тесты
│   │   ├── test_installer.py         # Установка, сохранение пользовательских данных, --force upgrade
│   │   ├── test_layout.py            # Проверка эталонной раскладки продукта, lock-файлов и навыков
│   │   └── test_validator_cli.py     # Тестирование команд CLI (validate, check-gate, validate-layout, lint-context)
│   ├── e2e/                          # Сквозные симуляции жизненного цикла
│   │   ├── test_golden_workflow.py   # Эталонный 8-шаговый цикл фичи от intake до archive
│   │   ├── test_noop_workflow.py     # Цикл невоспроизведённого бага (not-reproduced) и архивация
│   │   ├── test_terminal_workflows.py# Невоспроизводимые и отклонённые сценарии
│   │   └── test_failure_modes.py     # Негативные гейты, циклы задач, потеря/порча request.md
│   └── evals/                        # Тесты подсистемы LLM Evals
│       ├── test_dataset.py           # Валидация и загрузка датасета бенчмарков
│       ├── test_mock_provider.py     # Сценарии MockLLMProvider и RealLLMProvider
│       ├── test_eval_runner.py       # Движок выполнения и агрегация метрик
│       └── test_eval_cli.py          # Команда deltafuse eval, CLI аргументы и форматы экспорта
├── .github/workflows/test.yml        # CI матрица: Linux, Windows, macOS x Python 3.10-3.14
├── pyproject.toml                    # Конфигурация проекта, метаданных и pytest
└── tests/README.md                   # Руководство по запуску тестов и CLI
```

---

## 3. Детализированная матрица тестовых наборов

### Набор 1. Структурные тесты схем и шаблонов (`tests/unit/test_schemas.py`, `test_templates.py`)
* **1.1. Мета-схемы**: все 9 схем в `process/schemas/*.yaml` компилируются по стандарту JSON Schema Draft 2020-12.
* **1.2. Self-Validation шаблонов**: каждый файл-шаблон в `process/templates/**` на 100% валидируется своей схемой:
  - `change.yaml` -> `change.schema.yaml`
  - `tasks/TASK-001-template.md` (frontmatter) -> `task.schema.yaml`
  - `slices/SLICE-01.md` (frontmatter) -> `slice.schema.yaml`
  - `_capabilities.yaml` -> `capability.schema.yaml`
  - `decisions/DEC-0000-template.md` -> `decision.schema.yaml`
  - `evidence/red/evidence.yaml` -> `evidence.schema.yaml`
  - `coverage.yaml` -> `coverage.schema.yaml`
  - `routing.yaml` -> `routing.schema.yaml`
  - `spec-delta.md` (frontmatter) -> `spec-delta.schema.yaml`
* **1.3. Strict-режим (`unevaluatedProperties: false` / `additionalProperties: false`)**:
  - Подача лишних полей в корневые документы или frontmatter приводит к гарантированной ошибке валидации.

---

### Набор 2. Тесты графов, ссылочной целостности и якорей (`tests/unit/test_graph.py`, `test_integrity.py`)
* **2.1. DAG задач (Task Graph)**:
  - Топологическая сортировка задач по `depends_on`.
  - Обнаружение циклических зависимостей (`TASK-001 -> TASK-002 -> TASK-001`) с информативной ошибкой.
* **2.2. Спецификационные якоря (`spec_refs`)**:
  - Парсинг заголовков спецификаций (`# REQ-...`, `# SC-...`).
  - Проверка существования целевых якорей.
  - Path containment: `spec_refs` / `design_ref` after `resolve()` must stay inside the product repository root (`../` is rejected).
  - Spec-root guard (N10): если `docs/spec` отсутствует при наличии `spec_refs`, генерируется ошибка валидации, а не тихий пропуск.
* **2.3. Decision Anchors**:
  - Ссылка `design_ref: docs/decisions/DEC-...` требует статус решения `accepted`. Статусы `proposed` и `rejected` блокируют прохождение гейта `analyzed`/`specified`.

---

### Набор 3. Конечный автомат, семантические мутации и гейты (`tests/unit/test_fsm.py`, `test_fsm_mutations.py`)
* **3.1. 18 канонических статусов Change** (соответствуют `VALID_CHANGE_STATUSES` в `core/fsm.py` и `docs/state-machine.md`):
  - Вход: `normalized`.
  - Анализ: `analyzing`, `blocked-on-decision`, `analyzed`.
  - Спецификация и декомпозиция: `specification-proposed`, `specified`, `decomposed`.
  - Таргетинг и разработка: `targeting`, `target-confirmed`, `implementing`, `implemented`.
  - Верификация и завершение: `verifying`, `converged`, `archived`.
  - Терминальные ветви: `rejected`, `duplicate`, `superseded`, `not-reproduced`.
* **3.2. Семантические мутационные инварианты (T1–T8, N10)**:
  - **T1**: Зелёный отчет `phase: green` в папке `evidence/red/` строго отвергается.
  - **T2**: Red evidence с `result: passed` или `exit_code: 0` (кроме `not-reproduced` и `already-green`) отвергается.
  - **F-009 / targeting**: `already-green` допускается, если публичный оракул уже зелёный; Red-тест с доступом к `._` / `_private` отвергается.
  - **T3**: Гейт `converged` падает, если хотя бы одна задача осталась в незавершённом статусе (`pending`, `targeting` и т.д.). `cancelled` и `superseded` — терминалы (F-005 / RM-005); Verify не снимается.
  - **T4**: Evidence, ссылающееся на несуществующую задачу (в том числе при пустом каталоге `tasks/`), отклоняется.
  - **T5**: Несоответствие статуса `change.yaml` наличию артефактов (например, статус `normalized` при наличии задач или evidence) отклоняется.
  - **T7**: Битая ссылка на якорь в спецификации отклоняется.
  - **T8**: Повторная архивация при наличии существующего архива запрещена (неизменяемость архива, отказ от `rmtree`).
  - **N10**: Отсутствие каталога `docs/spec` при наличии ссылок на требования отвергается.
  - **F-010 / specified**: гейт `specified` требует живые файлы под `docs/spec/**`, валидный `_capabilities.yaml` и (для `none`) якоря в `spec_refs`; одного `spec-delta.md` недостаточно.
  - **F-006 / implemented, converged**: Green/regression/verification с `base_revision`, не совпадающим с хешем `docs/spec/**` + `src/**`, отвергаются (stale evidence).
  - **Q-008 / converged**: `spec-delta.md` `added`/`modified` должны существовать в `docs/spec/**`; `removed` не должны. Пакет без `spec-delta.md` (S04) не требует сверки. Архив не merge SSOT.
  - **Lock Hash**: Несовпадение `change.yaml.framework.content_hash` со значением из `.deltafuse/lock.yaml` отклоняется.

---

### Набор 4. Инсталлятор, целостность и раскладка (`tests/integration/test_installer.py`, `test_layout.py`)
* **4.1. Fresh Install**:
  - Разворачивание структуры `.deltafuse/`, `docs/{intake,changes,spec,decisions,archive}`, генерация адаптеров `.agents/`, `.cursor/`, `.gemini/`.
  - Проверка маркеров `# DO NOT EDIT: generated by DeltaFuse installer.` и метаданных `.deltafuse-generated.yaml`.
* **4.2. Идемпотентность и защита данных**:
  - Пользовательские спецификации, решения и конфиги не затираются при повторном запуске.
  - Флаг `--force` обновляет только управляемые фреймворком файлы.
* **4.3. Валидатор раскладки (`deltafuse validate-layout`)**:
  - Проверка структуры репозитория, соответствия `config.yaml` <-> `lock.yaml` (версия, источник, хэш), отсутствия легаси-каталогов (`docs/process`, `docs/init`, `docs/todo`).

---

### Набор 5. Контекстные бюджеты и контракты (`tests/unit/test_context.py`)
* **5.1. Token Estimator**:
  - Upper-bound estimator: EN prose `words * 1.3`; code ×2.7; YAML/JSON ×4.5; logs ×4.8; Cyrillic ×2.2. Optional `DELTAFUSE_TOKENIZE_URL` (`POST /tokenize`); never chat completions (Q-004).
  - Missing files and paths outside `repo_root` are errors, not silent skips; duplicate resolved paths count once.
* **5.2. Интеграция в FSM и CLI**:
  - Валидация frontmatter слайсов (`context_budget`) в `validate_change_package`.
  - **F-002 / decomposed, targeting, implemented**: TASK требует `context_budget`; `spec_refs`+`allowed_paths` не могут превышать бюджет; `changed_paths` сверяются с `PHASE_CONTRACTS` (не sandbox ADR/Pact). `deltafuse lint-context` проверяет и `tasks/`.
  - Команда `deltafuse lint-context <change_dir>`.

---

### Набор 6. E2E Сквозные сценарии (`tests/e2e/`)
* **6.1. Golden Workflow (`test_golden_workflow.py`)**:
  - 8-шаговый цикл: `intake -> analyze -> specify -> decompose -> target -> implement -> verify -> archive`.
* **6.2. No-op & Not-reproduced (`test_noop_workflow.py`)**:
  - Исследование багов, генерация `not-reproduced` evidence, переход Change в `not-reproduced`, архивация терминального пакета.
* **6.3. Failure Modes (`test_failure_modes.py`)**:
  - Проверка инварианта `request.md`: удаление файла или требований `CR-*` ломает пакет и выявляет orphan claims.
  - Циклические задачи блокируют гейт декомпозиции.

---

### Набор 7. LLM Evals бенчмаркинг (`tests/evals/`, `src/deltafuse/evals/`)
* **7.1. Датасет и метрики**:
  - Датасет `default_cases.yaml` с категориями feature, bug, vague, not_reproduced, scope_drift.
  - Расчёт метрик: Schema Compliance Rate, Gate Pass Rate, Routing Accuracy, Claim Extraction F1.
* **7.2. Провайдеры**:
  - `MockLLMProvider`: детерминированная симуляция сценариев (`golden`, `schema_violation`, `fsm_violation`, `routing_mismatch`, `claim_hallucination`) для CI.
  - `RealLLMProvider`: интеграция с удалёнными LLM через API-ключи окружения (`DELTAFUSE_API_KEY`, `OPENAI_API_KEY`).
* **7.3. CLI команда `deltafuse eval`**:
  - Флаги: `--scenario`, `--provider [mock|real]`, `--output [text|json|markdown]`, `--min-schema-compliance`, `--min-gate-pass-rate`.

---

## 4. Консольные команды для инженера и агентов

```bash
# 1. Запуск полного набора автоматических тестов (89 тестов)
python -m pytest -v

# 2. Проверка валидности Change-пакета
deltafuse validate docs/changes/CHG-001-test

# 3. Проверка гейта жизненного цикла
deltafuse check-gate docs/changes/CHG-001-test --gate decomposed

# 4. Архивация завершённого пакета
deltafuse archive docs/changes/CHG-001-test

# 5. Проверка эталонной структуры репозитория и адаптеров
deltafuse validate-layout .

# 6. Проверка контекстного бюджета пакета
deltafuse lint-context docs/changes/CHG-001-test

# 7. Запуск детерминированного бенчмарка LLM Evals
deltafuse eval --scenario golden --min-schema-compliance 100.0 --min-gate-pass-rate 100.0
```

---

## 5. Непрерывная интеграция (CI Matrix)

Тестовый комплекс выполняется в GitHub Actions (`.github/workflows/test.yml`) по матрице:
- **Операционные системы**: `ubuntu-latest`, `windows-latest`, `macos-latest`
- **Версии Python**: `3.10`, `3.11`, `3.12`, `3.13`, `3.14`
- **Шаги проверки**:
  1. `python -m pytest -v` (полный набор unit, integration, e2e, evals)
  2. `deltafuse eval --scenario golden --min-schema-compliance 100.0 --min-gate-pass-rate 100.0`
