# Детализированные пошаговые планы реализации тестового фреймворка DeltaFuse

---

## 📌 ЭТАП 1: Фундамент (Core Engine, Модели данных, Валидация Схем и Шаблонов)

### 1.1. Цель и границы этапа
Создать легковесный Python-пакет `deltafuse`, объявить конфигурацию проекта (`pyproject.toml`), реализовать загрузку/валидацию JSON Schema Draft 2020-12 и покрыть 100% unit-тестами все схемы и эталонные шаблоны фреймворка.

### 1.2. Пошаговые задачи
1. **Инициализация окружения (`pyproject.toml`)**:
   - Минимальные зависимости: `jsonschema>=4.20.0`, `pyyaml>=6.0.1`, `pytest>=8.0.0`.
   - Поддержка запуска через стандартный `python -m pytest` и современный `uv run pytest`.
2. **Ядро загрузки схем (`src/deltafuse/core/schemas.py`)**:
   - Автоматический поиск всех `process/schemas/*.schema.yaml`.
   - Регистрация схем с поддержкой `$defs`, `$ref` и формата Draft 2020-12.
   - Метод `validate_document(schema_name: str, data: dict) -> list[str]` (возвращает список читаемых ошибок).
3. **Парсер Markdown Frontmatter (`src/deltafuse/core/frontmatter.py`)**:
   - Надежное извлечение YAML-заголовков из `.md` файлов (`tasks/*.md`, `slices/*.md`, `decisions/*.md`).
   - Сохранение номеров строк для точной локализации ошибок.
4. **Unit-тесты валидации схем (`tests/unit/test_schemas.py`)**:
   - Проверка компиляции всех 7 схем: `change`, `capability`, `slice`, `task`, `evidence`, `decision`, `coverage`.
   - Негативные тесты для каждой схемы: передача некорректных enum, битых regex (`CR-01` вместо `CR-001`, `TASK-1` вместо `TASK-001`), лишних полей в `additionalProperties: false`.
5. **Unit-тесты валидации шаблонов (`tests/unit/test_templates.py`)**:
   - Прогон каждого файла из `process/templates/**` через соответствующую схему.
   - Гарантия: любой шаблон «из коробки» валиден на 100%.

### 1.3. Критерии приемки (Definition of Done)
- [x] `pytest tests/unit/test_schemas.py` и `pytest tests/unit/test_templates.py` выполняются быстрее чем за 1 секунду.
- [x] Покрытие кода тестами для `core/schemas.py` и `core/frontmatter.py` составляет 100%.

---

## 📌 ЭТАП 2: Кроссплатформенный Python-Инсталлятор и Интеграционные тесты

### 2.1. Цель и границы этапа
Заменить разрозненные скрипты `init.ps1` и `init.sh` на единый надежный Python-модуль `src/deltafuse/core/installer.py`. Покрыть интеграционными тестами установку, идемпотентность, хэширование и флаг `--force`.

### 2.2. Пошаговые задачи
1. **Калькулятор Content Hash (`src/deltafuse/core/hasher.py`)**:
   - Вычисление детерминированного `sha256` по содержимому всех файлов в каталоге `process/` (с нормализацией окончаний строк `CRLF` -> `LF` для идентичности на Windows/Linux/macOS).
2. **Кроссплатформенный установщик (`src/deltafuse/core/installer.py`)**:
   - Создание структуры целевого продукта (`.deltafuse/`, `docs/intake/`, `docs/changes/`, `docs/spec/`, `docs/decisions/`, `docs/archive/`).
   - Генерация `.deltafuse/lock.yaml` с версией и `content_hash`.
   - Генерация адаптеров для агентов (`.agents/skills/`, `.cursor/skills/`, `.gemini/skills/`).
   - Защита пользовательских файлов (не перезаписывать `_capabilities.yaml`, `config.yaml`, `AGENTS.md`, `CHANGELOG.md` при повторном запуске).
   - Обработка флага `--force`.
3. **CLI команда инициализации (`src/deltafuse/cli.py`)**:
   - Добавление команды `deltafuse init [--force] [--target <path>]`.
   - Тонкие обертки-заглушки для `init.ps1` и `init.sh` (вызывающие Python-модуль, сохраняя обратную совместимость для старых скриптов).
4. **Интеграционные тесты инсталлятора (`tests/integration/test_installer.py`)**:
   - `test_fresh_install`: установка в пустой `tmp_path`, проверка структуры и прав доступа.
   - `test_idempotent_upgrade_without_force`: проверка сохранности кастомных пользовательских правок.
   - `test_force_upgrade`: обновление только ядра фреймворка без затирания спеки.
   - `test_hash_consistency`: проверка идентичности вычисленного хэша на Windows и Linux.

### 2.3. Критерии приемки
- [x] `pytest tests/integration/test_installer.py` полностью заменяет функционал `tests/smoke-test.ps1` и `tests/smoke-test.sh`.
- [ ] Тесты инсталлятора стабильно проходят на любой ОС без внешних зависимостей шеллов.

---

## 📌 ЭТАП 3: Движок валидации, DAG графы, FSM гейты и CLI Tooling

### 3.1. Цель и границы этапа
Создать аналитический движок, способный проверять целостность связей, ацикличность графа задач и допустимость переходов между статусами жизненного цикла. Дать агентам команду `deltafuse validate` и `deltafuse check-gate`.

### 3.2. Пошаговые задачи
1. **DAG Анализатор задач (`src/deltafuse/core/graph.py`)**:
   - Построение графа зависимостей по полям `depends_on` в `tasks/TASK-*.md` и `slices/SLICE-*.md`.
   - Алгоритм Тарьяна / Kahn для поиска циклов (`CycleDetectionError`).
   - Топологическая сортировка: выдача списка задач в правильном порядке выполнения.
2. **Анализатор ссылочной целостности (`src/deltafuse/core/integrity.py`)**:
   - Парсер заголовков и якорей `REQ-*`, `SC-*`, `DEC-*` в `docs/spec/**` и `docs/decisions/**`.
   - Проверка, что каждый `spec_ref` в задаче или слайсе реально существует.
   - Проверка полноты матрицы `coverage.yaml`: отсутствие сиротских (orphan) `CR-*` и незакрытых задач.
3. **Движок конечного автомата (`src/deltafuse/core/fsm.py`)**:
   - Таблица допустимых переходов для `change.yaml` и `slices/*.md`.
   - Проверка условий гейтов:
     - Gate *Analyzed*: все claims распределены, `coverage.yaml` валиден, нет неразрешенных блокирующих решений.
     - Gate *Specified*: есть `spec-delta.md` (или proof неизменности для багов).
     - Gate *Target Confirmed*: наличие `evidence/red/TASK-*.yaml` со статусом `expected-failure`.
     - Gate *Implemented*: наличие `green` и `regression` evidence с кодом `0`.
     - Gate *Converged*: все задачи закрыты, зафиксирован `verification/run.yaml`.
4. **CLI команды валидации и архивации (`src/deltafuse/cli.py`)**:
   - `deltafuse validate --change <id>` (полная статическая проверка пакета изменений).
   - `deltafuse check-gate --change <id> --gate <gate-name>` (проверка готовности к следующему шагу).
   - `deltafuse archive --change <id>` (проверка сходимости и перемещение пакета в `docs/archive/changes/YYYY-MM-DD-<change-id>/`).
5. **Unit & Integration тесты валидатора (`tests/unit/test_fsm.py`, `test_dag.py`, `test_integrity.py`)**:
   - Тесты на обнаружение циклических зависимостей.
   - Тесты на отказ в переходе при отсутствии обязательных evidence файлов.
   - Тесты на обнаружение битых ссылок на спеку.

### 3.3. Критерии приемки
- [ ] Любое нарушение инвариантов фреймворка мгновенно детектируется с понятным указанием файла и причины.
- [ ] Агент получает инструмент мгновенной самопроверки перед вызовом следующего скилла.

---

## 📌 ЭТАП 4: Детерминированные сквозные симуляции (E2E Synthetic Replays)

### 4.1. Цель и границы этапа
Создать набор синтетических фикстур, воспроизводящих реальные сценарии изменений (Feature, Bug, Not-Reproduced, Duplicate, Blocked-on-Decision), и протестировать сквозной путь от `intake` до перемещения в `docs/archive/changes/`.

### 4.2. Пошаговые задачи
1. **Подготовка синтетических фикстур (`tests/e2e_replays/fixtures/`)**:
   - `fixture_standard_feature/`: нормализация требования, 2 слайса, 3 задачи, Red/Green evidence, верификация, архивация.
   - `fixture_implementation_bug/`: баг без изменения спеки (`spec-delta.md` с доказательством), 1 задача фикса, TDD Red/Green evidence.
   - `fixture_not_reproduced/`: баг, который не удалось воспроизвести на шаге Target (формирование отчета, закрытие в `not-reproduced`).
   - `fixture_blocked_on_decision/`: изменение, требующее архитектурного решения (блокировка на гейте до перевода `DEC-*` в `accepted`).
2. **Сквозной раннер симуляций (`tests/e2e_replays/test_lifecycle_replays.py`)**:
   - Пошаговое разворачивание артефактов в изолированном `tmp_path`.
   - Проверка, что на каждом шаге `deltafuse check-gate` разрешает строго допустимые действия.
   - Тестирование команды `deltafuse archive --change <id>`:
     - Проверка создания `docs/archive/changes/YYYY-MM-DD-CHG-XXX/`.
     - Проверка очистки активной папки `docs/changes/`.
     - Проверка перевода `change.yaml` в статус `archived`.

### 4.3. Критерии приемки
- [ ] Все ключевые сценарии жизненного цикла (Feature, Bug, No-op, Rejected, Not-reproduced) воспроизводятся детерминированно за 2–3 секунды в CI.

---

## 📌 ЭТАП 5: Контекстные линтеры, CI/CD и Интеграция в Скиллы

### 5.1. Цель и границы этапа
Интегрировать валидатор в скиллы агентов (`process/skills/**/SKILL.md`), автоматизировать проверки в CI/CD (GitHub Actions / GitLab CI) и реализовать контроль контекстных бюджетов.

### 5.2. Пошаговые задачи
1. **Контекстный линтер (`src/deltafuse/core/context.py`)**:
   - Проверка соответствия `Context Contract` по таблице допустимых путей чтения.
   - Расчет размера контекста: проверка непревышения `max_tokens` и `max_files` из `.deltafuse/config.yaml`.
2. **Обновление инструкций скиллов (`process/skills/`)**:
   - Добавление в шаги скиллов рекомендации по запуску локального валидатора перед сдачей артефактов:
     ```bash
     python -m deltafuse check-gate --change CHG-XXX --gate <current-step>
     ```
3. **Настройка CI/CD (`.github/workflows/test.yml` / `.gitlab-ci.yml`)**:
   - Матричный запуск на `ubuntu-latest`, `windows-latest`, `macos-latest`.
   - Запуск через `uv run pytest --cov=src/deltafuse --cov-report=term-missing`.
   - Блокировка PR при падении тестов или нарушении покрытия.

### 5.3. Критерии приемки
- [ ] Полный комплекс тестов автоматически запускается в CI.
- [ ] Все скиллы содержат четкую инструкцию по самопроверке агентом через встроенный валидатор.
