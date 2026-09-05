# Стратегия и план комплексного тестирования DeltaFuse 2.0

> **Цель**: Построить модульный, детерминированный, кроссплатформенный комплекс тестов и инструментов верификации на базе **Python 3.10+ / pytest**, исключающий дублирование шелл-скриптов (`pwsh`/`bash`), обеспечивающий 100% контроль инвариантов фреймворка и служащий быстрым feedback-loop валидатором для LLM-агентов.

---

## 1. Архитектурная пирамида тестирования

```
                     ┌───────────────────────────────┐
                     │          LLM Evals            │  <- Оценка моделей & промптов
                     │   (Prompt Benchmarks / E2E)   │     (5-10% скоупа, опционально)
                     ├───────────────────────────────┤
                     │     E2E Synthetic Flows       │  <- Полный цикл Intake -> Archive
                     │    (Deterministic Replays)    │     на синтетических фикстурах (15%)
                     ├───────────────────────────────┤
                     │    Workflow & State Machine   │  <- FSM, гейты, DAG зависимостей,
                     │       (Process Invariants)    │     матрица покрытия (25%)
                     ├───────────────────────────────┤
                     │   Schema, Layout & Contracts  │  <- Валидация YAML, Frontmatter,
                     │      (Structural Invariants)  │     хэшей, установщика (50%)
                     └───────────────────────────────┘
```

---

## 2. Структура тестового фреймворка (`delta-fuse/tests/`)

Предлагается единая раскладка тестов и тулинга:

```text
delta-fuse/
├── src/deltafuse/                    # Легковесный движок валидатора и CLI
│   ├── __init__.py
│   ├── cli.py                        # Точка входа: df init, df validate, df check-gate
│   ├── core/
│   │   ├── hasher.py                 # Вычисление sha256 framework content hash
│   │   ├── installer.py              # Кроссплатформенная установка/обновление
│   │   ├── schemas.py                # Загрузчик и валидатор JSON Schema 2020-12
│   │   ├── frontmatter.py            # Парсер Markdown + YAML frontmatter
│   │   ├── fsm.py                    # Движок переходов состояний (State Machine)
│   │   ├── graph.py                  # DAG анализатор зависимостей (cycle detection)
│   │   └── context.py                # Калькулятор токенов и линтер контекстных контрактов
│   └── models/                       # Pydantic / TypedDict модели данных
│       ├── change.py
│       ├── task.py
│       ├── slice.py
│       ├── capability.py
│       └── evidence.py
├── tests/
│   ├── conftest.py                   # Общие pytest фикстуры, моки файловой системы (tmp_path)
│   ├── unit/                         # Модульные тесты
│   │   ├── test_content_hash.py      # Хэширование дистрибутива
│   │   ├── test_schemas.py           # Валидация самих схем и их рекурсивных $defs
│   │   ├── test_templates.py         # Проверка, что все process/templates валидны
│   │   ├── test_frontmatter_parser.py
│   │   ├── test_dag_dependencies.py  # Топологическая сортировка и циклы в TASK-NNN
│   │   └── test_state_machine.py     # Все валидные и невалидные переходы Change/Slice
│   ├── integration/                  # Интеграционные тесты
│   │   ├── test_installer.py         # Свежая установка, сохранение пользовательских файлов
│   │   ├── test_idempotent_upgrade.py# Повторный накакт, флаг force, lock.yaml
│   │   ├── test_layout_validator.py  # Проверка эталонной структуры продукта
│   │   └── test_link_integrity.py    # Ссылочная целостность REQ-* / DEC-* / CR-*
│   ├── e2e_replays/                  # Сквозные синтетические симуляции без LLM
│   │   ├── fixtures/
│   │   │   ├── feature_standard/     # Эталонный прогон фичи: от intake до archive
│   │   │   ├── bug_implementation/   # Эталонный баг (spec unchanged -> red -> green)
│   │   │   └── not_reproduced_flow/  # Закрытие невоспроизведенного бага
│   │   └── test_lifecycle_replays.py
│   └── evals/                        # LLM Evals (тестирование реальных моделей)
│       ├── cases/                    # Набор сырых пользовательских тикетов
│       └── test_agent_routing_eval.py# Сравнение вывода агента с Ground Truth
├── pyproject.toml                    # Конфигурация uv/poetry/pytest
└── requirements-dev.txt              # pytest, jsonschema, pyyaml
```

---

## 3. Детализированная матрица тестовых наборов

### Набор 1. Структурные тесты схем и шаблонов (`tests/unit/test_schemas.py`, `test_templates.py`)
* **1.1. Мета-схемы**: проверка, что все схемы в `process/schemas/*.yaml` компилируются по стандарту JSON Schema 2020-12.
* **1.2. Self-Validation шаблонов**: каждый файл-шаблон в `process/templates/**` обязан на 100% валидироваться своей схемой:
  - `change.yaml` -> `change.schema.yaml`
  - `tasks/TASK-001-template.md` (frontmatter) -> `task.schema.yaml`
  - `slices/SLICE-01.md` (frontmatter) -> `slice.schema.yaml`
  - `_capabilities.yaml` -> `capability.schema.yaml`
  - `decisions/DEC-0000-template.md` -> `decision.schema.yaml`
  - `evidence/red/evidence.yaml` -> `evidence.schema.yaml`
  - `coverage.yaml` -> `coverage.schema.yaml`
  - `routing.yaml` -> `routing.schema.yaml`
  - `spec-delta.md` (frontmatter) -> `spec-delta.schema.yaml`
* **1.3. Strict-режим (`additionalProperties: false`)**:
  - Подача YAML с лишними ключами (`foo: bar`) обязана приводить к падению теста.

---

### Набор 2. Тесты графов, ссылок и матрицы покрытия (`tests/unit/test_dag_dependencies.py`, `tests/integration/test_link_integrity.py`)
* **2.1. DAG задач (Task Graph)**:
  - Проверка на отсутствие циклов (`TASK-001 -> TASK-002 -> TASK-001`).
  - Проверка, что `TASK-002` не может быть взят в работу, пока `TASK-001` не находится в статусе `implemented`/`verified`.
* **2.2. Полнота трассируемости матрицы (`coverage.yaml`)**:
  - Каждый `CR-*` из `request.md` обязан присутствовать в `coverage.yaml`.
  - Каждый `CR-*` обязан быть привязан ровно к одному primary slice.
  - Каждое требование `spec_refs` обязано существовать как физический якорь `#REQ-...` в файлах `docs/spec/**`.
* **2.3. Decision Anchors**:
  - Если в задаче или слайсе указан `design_ref: docs/decisions/DEC-0001-...md`, валидатор проверяет, что решение имеет статус `accepted` (не `proposed` и не `rejected`).

---

### Набор 3. Тесты конечного автомата (State Machine Transitions) (`tests/unit/test_state_machine.py`)
* **3.1. Матрица положительных переходов**:
  - `normalized -> analyzing` (при наличии `request.md` с валидными `CR-001`).
  - `analyzing -> analyzed` (при наличии `routing.yaml` и валидных `slices/**`).
  - `analyzed -> specified` (при наличии `spec-delta.md`).
  - `specified -> decomposed` (при наличии задач `TASK-*`).
  - `decomposed -> targeting` (при выборе готовой задачи).
  - `targeting -> target-confirmed` (при наличии Red evidence `result: expected-failure`).
  - `target-confirmed -> implementing -> implemented` (при наличии Green `result: passed` + Regression `result: passed`).
  - `implemented -> verifying -> converged -> archived` (перемещение в `docs/archive/changes/<date>-<change-id>/`).
* **3.2. Негативные гейты (Отказ в переходе)**:
  - Попытка перевести в `implemented`, если `evidence.exit_code != 0`.
  - Попытка перевести в `specified`, если есть неразрешённые `DEC-*` в статусе `proposed`.
  - Попытка перевести в `converged`, если хотя бы одна задача пакета осталась в `targeting` или `draft`.
* **3.3. Специальные пути (Bugflow, Not-reproduced, Rejected)**:
  - Implementation Bug: `analyzed -> specified (delta: none) -> decomposed -> targeting`.
  - Not reproduced: переход в `not-reproduced` из `analyzing`, `targeting` и `verifying`.

---

### Набор 4. Тесты инсталлятора, обновления и целостности (`tests/integration/test_installer.py`)
* **4.1. Fresh Install**:
  - Установка в чистую директорию `tmp_path`.
  - Проверка создания структуры: `.deltafuse/`, `docs/intake/`, `docs/changes/`, `docs/spec/`, `docs/decisions/`, `docs/archive/`.
  - Генерация адаптеров `.agents/skills/`, `.cursor/skills/`, `.gemini/skills/`.
* **4.2. Идемпотентность и защита пользовательских данных**:
  - Модификация `AGENTS.md`, `.deltafuse/config.yaml`, `docs/spec/_capabilities.yaml` в проекте.
  - Запуск повторной установки: кастомный контент **не перезаписывается**.
  - Запуск с флагом `--force`: обновление только framework core файлов, пользовательские спецификации остаются нетронутыми.
* **4.3. Хэш-фиксация (`content_hash`)**:
  - Изменение любого файла в `process/` приводит к изменению `sha256` хэша фреймворка.
  - Попытка запуска Change с несовпадающим хэшем выдает предупреждение / блокировку миграции.

---

### Набор 5. Контекстные бюджеты и контракты (`tests/unit/test_context_contracts.py`)
* **5.1. Context Budget Checker**:
  - Подсчет токенов (через `tiktoken` или эвристику слов) по списку файлов.
  - Если слайс требует загрузить файлов больше, чем `max_files: 24`, тест генерирует флаг `context-overflow` (требование дополнительной декомпозиции).
* **5.2. Scope Drift Linter**:
  - Проверка по git diff: если задача объявляет `allowed_paths: [src/auth/*]`, а изменены файлы в `src/billing/*` — валидатор возвращает фатальную ошибку `Scope Drift Violation`.

---

### Набор 6. E2E Synthetic Replay Tests (`tests/e2e_replays/`)
* **6.1. Полный сквозной сценарий (Feature Replay)**:
  - Создание фикстуры `CHG-001`.
  - Пошаговое накладывание файлов (`request.md` -> `analysis.md` + `slices/` -> `spec-delta.md` -> `tasks/` -> `evidence/red/` -> `code fix` + `evidence/green/` -> `verification.md`).
  - Вызов `deltafuse archive CHG-001`.
  - Проверка: директория переместилась в `docs/archive/changes/2026-09-04-CHG-001/`, в активном `docs/changes/` чисто, `change.yaml` в статусе `archived`.

---

### Набор 7. LLM Eval Benchmarks (Опциональный слой оценки моделей)
* **7.1. Intake & Routing Accuracy**:
  - Подача 10 тестовых пользовательских описаний фич/багов.
  - Запуск агента через API.
  - Проверка: сопоставил ли агент тикет с правильной `primary_capability` из каталога `_capabilities.yaml`.
* **7.2. Red-TDD Verification**:
  - Проверка, что агент написал тест, который реально падает на существующей кодовой базе с кодом `1` и понятным assertion.

---

## 4. План реализации по этапам (Roadmap)

| Этап | Скоуп работ | Результат |
|---|---|---|
| **Этап 1: Фундамент (Core CLI & Schemas)** | 1. Настройка `pyproject.toml` (pytest, jsonschema, pyyaml).<br>2. Создание `src/deltafuse/core/schemas.py` и `hasher.py`.<br>3. Unit-тесты для всех схем и шаблонов. | `pytest tests/unit/test_schemas.py` проходит за < 1 сек. |
| **Этап 2: Кроссплатформенный инсталлятор** | 1. Реализация `src/deltafuse/core/installer.py` (замена `init.ps1`/`init.sh`).<br>2. Интеграционные тесты `test_installer.py` (fresh install, idempotent, upgrade). | Полный отказ от шелл-скриптов, единый `df init` / `python -m deltafuse init`. |
| **Этап 3: Движок валидации и гейтов (Linters & FSM)** | 1. Реализация `frontmatter.py`, `graph.py` (DAG), `fsm.py` (переходы).<br>2. Реализация команды `df validate` и `df check-gate`.<br>3. Тесты на циклы, битые ссылки, матрицу переходов. | Агент может вызывать `df validate` как мгновенный feedback-loop. |
| **Этап 4: E2E Replays & Сквозные сценарии** | 1. Создание каталога фикстур `tests/e2e_replays/fixtures/`.<br>2. Сквозной тест жизненного цикла (Feature, Bug, No-op). | 100% гарантия надежности перед любыми релизами фреймворка. |
| **Этап 5: CI/CD Pipeline** | Настройка GitHub Actions / GitLab CI workflow (`python -m pytest tests/ -v`). | Зелёный статус в CI на Linux, Windows и macOS. |

---

## 5. Команда быстрого запуска для разработчика / агента

```bash
# Запуск всех детерминированных тестов (мгновенно, без LLM)
pytest tests/unit tests/integration -v

# Проверка конкретного Change агентом на лету
python -m deltafuse validate --change CHG-001 --gate decomposed

# Сквозной запуск симуляций
pytest tests/e2e_replays/ -v
```
