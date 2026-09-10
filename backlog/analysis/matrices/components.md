# Карта компонентов DeltaFuse

Критерий **BASE-002**: перечислить компоненты и связи между слоями, не подменяя наличие кода доказательством исполнения. Ревизия аудита: `60ea40438b0142797848356c660ab88286565e7d`; HEAD при инвентаризации: `cd536a75ee499d92a7dc467627725b53e841a22e`. Отличий вне backlog между ними нет.

Evidence: [inventory.json](../experiments/A00-02/inventory.json) — 116 путей, SHA-256 и размеры; [symbols.txt](../experiments/A00-02/symbols.txt) — определения; [headings.txt](../experiments/A00-02/headings.txt) — заголовки и metadata; [excerpts.json](../experiments/A00-02/excerpts.json) — точные фрагменты для наблюдений.

## Как читать карту

- **Контракт:** нормативный документ, skill, schema или template существует; согласованность проверяется позднее.
- **Код найден:** точка реализации/CLI и связанные тестовые файлы существуют; поведение не запускалось.
- **Заглушка:** в проверенном участке нет реализации заявленного вызова.
- **Исполнено:** для поведения фреймворка в A00-02 таких результатов нет. Pytest, smoke, layout и LLM-прогоны имеют `not-tested`.

Связь с тестом означает релевантное место для дальнейшей проверки, а не доказанное покрытие инварианта. Связь со схемой означает формат артефакта, а не семантическую гарантию.

## Инвентаризация

| Группа | Файлов | Состав и назначение |
|---|---:|---|
| Корень выбранной области | 5 | AGENTS, README EN/RU, VERSION, pyproject |
| `docs/` | 13 | README EN/RU; пять пар canonical docs; testing-strategy |
| `process/skills/` | 7 | По одному контракту на lifecycle-фазу |
| `process/schemas/` | 9 | YAML-описания структур Change и связанных артефактов |
| `process/templates/` | 25 | 12 файлов Change; 10 файлов product docs; AGENTS, CHANGELOG и скрытый config |
| `src/` | 21 | 20 Python-файлов и YAML dataset evals |
| `scripts/` | 2 | Самостоятельные установщики PowerShell и Bash |
| `tests/` | 32 | 20 test-модулей, 7 support-файлов, README, 2 smoke и 2 layout scripts |
| `.github/` | 2 | CI workflow и Copilot instruction pointer |
| **Всего** | **116** | Все tracked files в выбранных областях; backlog и локальные игнорируемые файлы не входят |

Это карта выбранных компонентов, а не утверждение, что во всём репозитории ровно 116 файлов. Использован `git ls-files`, поэтому скрытый `process/templates/.deltafuse/config.yaml` учтён.

## Канонические документы

Для пяти основных документов существуют EN/RU пары. Здесь оценивается наличие, а не эквивалентность перевода.

| Документ в `docs/` | Связь с другими слоями | Продолжение |
|---|---|---|
| `workflow.md`, `workflow.ru.md` | Семь skills; FSM, task/evidence/coverage; e2e tests | A02, A04, A05, A07 |
| `state-machine.md`, `state-machine.ru.md` | Статусы schema, `core/fsm.py`, terminal workflow tests | A02 |
| `roles.md`, `roles.ru.md` | Authority/human decisions в skills и Decision schema | A01, A02, A06 |
| `context-model.md`, `context-model.ru.md` | Контекст skills, config, `core/context.py`, context tests | A02-01, A03 |
| `using.md`, `using.ru.md` | Pin/lock, installer, scripts, layout validators | A02-10, A06 |
| `testing-strategy.md` | Target/Implement/Verify, evidence и тестовые наборы | A01-03, A07 |
| `README.md`, `README.ru.md` | Индекс canonical docs и граница framework/product | Навигация |

Корневые README представляют назначение и установку; `AGENTS.md` задаёт правила работы в canonical repository. `.github/copilot-instructions.md` отсылает к AGENTS и не является отдельной реализацией lifecycle.

## Семь фаз: doc → skill → artifact → runtime/test

Базовый doc — `docs/workflow.md`, секции 1–7. Все skill-пути ниже находятся в `process/skills/<имя>/SKILL.md`; schema — в `process/schemas/`; Change templates — в `process/templates/change/`.

| Фаза | Skill | Основные schema / templates | Кандидаты runtime и tests |
|---|---|---|---|
| Intake | `intake` | change / change.yaml, request.md | `fsm.validate_change_package/check_gate`; test_fsm, test_golden_workflow |
| Route and Analyze | `analyze-change` | routing, slice, capability, decision, coverage / routing.yaml, slices/SLICE-01.md, analysis.md, design.md, coverage.yaml | `fsm`, `integrity`, `graph`, `context`; test_integrity, test_graph, test_failure_modes |
| Specify | `specify-change` | spec-delta, decision / spec-delta.md; product spec/Decision templates | `fsm`, `integrity.validate_spec_ref/validate_decision_ref`; test_fsm, test_integrity, test_noop_workflow |
| Decompose | `decompose-change` | task, slice / tasks/TASK-001-template.md, slices/SLICE-01.md | `graph.topological_sort`, `fsm`; test_graph, test_fsm |
| Target | `target-task` | task, evidence / evidence/red/evidence.yaml | `fsm.check_gate`; test_fsm_mutations, test_golden_workflow |
| Implement | `implement-task` | task, evidence / evidence/green/evidence.yaml | `fsm.check_gate`; test_fsm_mutations, test_golden_workflow |
| Verify, Converge and Archive | `verify-change` | coverage, change, evidence / coverage.yaml, verification.md | `fsm`, `integrity.validate_coverage_completeness`, `archiver.archive_change`; test_golden_workflow, test_terminal_workflows |

Red и Green — evidence states внутри Target и Implement. Наличие семи текстовых skills не доказывает, что CLI самостоятельно исполняет семь агентных фаз; интерфейс CLI перечислен отдельно.

## Девять схем и шаблоны

| Schema-файл в `process/schemas/` | Связанный template в `process/templates/` |
|---|---|
| `change.schema.yaml` | `change/change.yaml` |
| `routing.schema.yaml` | `change/routing.yaml` |
| `slice.schema.yaml` | `change/slices/SLICE-01.md` |
| `spec-delta.schema.yaml` | `change/spec-delta.md` |
| `task.schema.yaml` | `change/tasks/TASK-001-template.md` |
| `evidence.schema.yaml` | `change/evidence/red/evidence.yaml`, `change/evidence/green/evidence.yaml` |
| `coverage.schema.yaml` | `change/coverage.yaml` |
| `capability.schema.yaml` | `docs/spec/_capabilities.yaml` |
| `decision.schema.yaml` | `docs/decisions/DEC-0000-template.md` |

Остальные Change templates: request, analysis, design, verification. Product docs включают README для intake/changes/spec/decisions/archive, spec context и каталог. Их полный перечень есть в inventory. Наличие template не означает его автоматическое копирование при init: это проверяется в A06-02.

## Python runtime и CLI

Точки входа: `pyproject.toml:21-22` → `deltafuse.cli:main`; `src/deltafuse/__main__.py` → тот же main. В CLI найдены семь команд, совпадение их числа с числом lifecycle-фаз не означает соответствия один к одному.

| CLI-команда | Реализация / назначение по dispatch и определениям | Основной тестовый адрес |
|---|---|---|
| `init` | `core/installer.py:install` — product layout, pin/lock, generated adapters | tests/integration/test_installer.py |
| `validate` | `core/fsm.py:validate_change_package` — пакет Change | tests/integration/test_validator_cli.py |
| `check-gate` | `core/fsm.py:check_gate` — preconditions выбранного gate | tests/unit/test_fsm.py, test_fsm_mutations.py |
| `archive` | `core/archiver.py:archive_change` — архив Change | tests/e2e/test_golden_workflow.py, test_terminal_workflows.py |
| `validate-layout` | `core/layout.py:validate_product_layout` — продукт и интеграция | tests/integration/test_layout.py |
| `lint-context` | `core/context.py:validate_context_budget` — бюджет refs | tests/unit/test_context.py |
| `eval` | `evals/dataset.py` → providers → runner → metrics/reporter | tests/evals/test_eval_cli.py, test_eval_runner.py |

Вспомогательные модули: `core/schemas.py` (SchemaRegistry); `frontmatter.py` (YAML frontmatter); `integrity.py` (claims/spec/Decision/coverage refs); `graph.py` (dependency sort); `hasher.py` (file/framework hash). В `context.py` найдены estimate_tokens/estimate_files_tokens, но погрешность и полнота prompt в этой задаче не измеряются.

### Генерация skills и установка

`core/installer.py:63-109` содержит копирование skill и вставку DO NOT EDIT/version/source/hash, а также marker metadata. `scripts/init.ps1` и `scripts/init.sh` содержат собственные операции копирования и маркировки. Это три пути реализации для A06, их эквивалентность не доказана.

Shell smoke вызывает соответствующий shell installer и layout validator, включая повторную установку. Python layout/installer проверяются отдельными integration tests. Обе платформы остаются `not-tested` до A00-04/05.

### Evals и локальная модель

| Компонент | Подтверждённое статическое наблюдение | Значение для очереди |
|---|---|---|
| `MockLLMProvider` | Класс существует; CLI выбирает его по умолчанию, доступны synthetic scenarios | Mock-успех не равен LLM-успеху |
| `CallableLLMProvider` | `providers.py:315-325` передаёт вызов переданному generator | Возможная программная точка подключения; готовый LM Studio provider не подтверждён |
| `RealLLMProvider` | `providers.py:328-347`: без key — RuntimeError; с key — NotImplementedError | Заглушка в проверенной реализации; A08-01 должен определить реальный путь |
| CLI provider selection | `cli.py:60,164-167`: только mock/real | Callable не выбирается этим CLI-параметром |
| Dataset/runner/metrics/reporter | Определения и тестовые модули найдены; dataset лежит в evals/data/default_cases.yaml | Проверка oracles и качества продукта — A07–A09 |

A03-03/A03-04 проверяют реальный профиль и анализ через LM Studio; A08-01 может подготовить экспериментальный harness через callable. Подключение не реализуется в задаче карты.

## Тесты и CI

| Группа | Test-модулей | Область |
|---|---:|---|
| Unit | 9 | context, frontmatter, fsm, fsm_mutations, graph, hasher, integrity, schemas, templates |
| Integration | 3 | installer, layout, validator_cli |
| E2E | 4 | golden, noop, failure_modes, terminal_workflows |
| Evals | 4 | dataset, mock_provider, eval_runner, eval_cli |

Fixtures: `tests/fixtures/change_builder.py`, `tests/conftest.py`; support __init__ не считаются test-модулями. Число pytest cases и их исходы пока неизвестны.

`.github/workflows/test.yml` задаёт три OS × пять Python (3.10–3.14), pytest и golden eval с порогами schema/gate по 100%. Provider в команде CI не задан; default CLI — mock. Это конфигурация 15 комбинаций, а не свидетельство успешного текущего CI. Новые CI-логи не запрашивались.

## Наблюдения для следующих карточек

| ID | Наблюдение и предел вывода | Продолжение |
|---|---|---|
| MAP-OBS-001 | Подтверждена заглушка RealLLMProvider; callable является extension point, а не готовой интеграцией | A03-03/04, A08-01 |
| MAP-OBS-002 | В tests/README.md есть `--threshold`; в проверенном argparse-блоке eval такого параметра нет | A02-10; запуск команды ещё не выполнен |
| MAP-OBS-003 | Tests README описывает «8-step lifecycle», canonical workflow содержит семь фаз; индекс tests не перечисляет context/hasher/templates/terminal_workflows | A02-10; неполный обзор сам по себе не доказывает runtime-дефект |
| MAP-OBS-004 | Installer/hasher/layout представлены несколькими платформенными реализациями | A06-01/02; наличие нескольких реализаций не доказывает их расхождение |

Наблюдения имеют точные исходные адреса, но не оформлены как семантические дефекты фреймворка без проверок соответствующих карточек.
