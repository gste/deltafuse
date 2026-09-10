# Результат эксперимента A06-01

- **ID карточки:** A06-01
- **Ревизия:** `615fd4c94025a176ce5b14fca75a5e3ecde30932`
- **Критерии:** `CODE-005` (Type Safety & Static Hygiene), `CODE-006` (Explicit Error Handling), `PROC-002` (FSM Determinism)
- **Вердикт:** **pass** (границы модулей строго очерчены, дублирование статусов отсутствует, Single Source of Truth для схем соблюдён)

## Ожидаемое поведение

1. **Разделение ответственности и модульные границы**:
   - `src/deltafuse/core/schemas.py`: отвечает исключительно за загрузку метасхем JSON Schema Draft 2020-12, компиляцию валидаторов и форматирование ошибок валидации.
   - `src/deltafuse/core/frontmatter.py`: парсит YAML frontmatter в Markdown-документах без привязки к конкретным бизнес-схемам.
   - `src/deltafuse/cli.py`: диспетчеризует аргументы командной строки в соответствующие модули ядра (`installer`, `fsm`, `layout`, `archiver`, `context`, `evals`) и возвращает канонические exit codes.
   - `src/deltafuse/core/layout.py`: изолированно верифицирует файловую структуру продукта, lock-файл и маркеры сгенерированных навыков.
2. **Single Source of Truth (SSOT)**:
   - Статусы жизненного цикла Change (`VALID_CHANGE_STATUSES` в `fsm.py`) должны быть строго согласованы со схемой `process/schemas/change.schema.yaml`.
   - Версии фреймворка должны резолвиться из канонического источника (`VERSION` / `pyproject.toml` / `__version__`).
3. **Качество диагностики (Diagnostics Quality)**:
   - Ошибки валидации схем должны указывать точный путь до ошибочного свойства (`[root]`, `[slices -> 0 -> id]`), а не падать с неинформативными stack trace.

## Наблюдаемое поведение

1. **Сверка канонических статусов FSM vs Change Schema**:
   - В `src/deltafuse/core/fsm.py` определены ровно 18 допустимых статусов (`VALID_CHANGE_STATUSES`).
   - В `process/schemas/change.schema.yaml` в перечислении `properties.status.enum` также определены ровно те же 18 статусов:
     `[normalized, analyzing, blocked-on-decision, analyzed, specification-proposed, specified, decomposed, targeting, target-confirmed, implementing, implemented, verifying, converged, archived, rejected, duplicate, not-reproduced, superseded]`.
   - Симметрическая разность множеств: `diff = VALID_CHANGE_STATUSES.symmetric_difference(schema_statuses) == set()` (0 расхождений).
2. **Единство версий**:
   - `VERSION` содержит `2.0.0`.
   - `pyproject.toml` содержит `version = "2.0.0"`.
   - `src/deltafuse/__init__.py` содержит `__version__ = "2.0.0"`.
   - Инсталлятор `installer.py` динамически считывает версию из файла `VERSION` фреймворка, исключая хардкод версий в коде создания артефактов.
3. **Качество диагностики SchemaRegistry**:
   - Ошибки валидации форматируются методом `iter_errors` с извлечением пути: `f"[{path_str}] {error.message}"`.
   - При валидации пустого объекта против схемы `change` генерируется точный список из 9 пропущенных обязательных полей с корневым указателем:
     `["[root] 'id' is a required property", "[root] 'title' is a required property", ...]`.
4. **Архитектурная чистота CLI**:
   - `cli.py` не реализует доменную бизнес-логику внутри себя; все команды делегируются в чистые функции (`install`, `validate_change_package`, `check_gate`, `archive_change`, `validate_product_layout`, `validate_context_budget`).
   - CLI перехватывает доменные исключения (`InstallationError`, `ArchivalError`) и корректно форматирует их в `sys.stderr` с кодом возврата 1 (пользовательская/бизнес-ошибка) или 2 (непредвиденная системная ошибка).

## Ограничения

- Загрузка схем в `SchemaRegistry` по умолчанию опирается на относительный поиск `process/schemas` от корня репозитория либо `Path(__file__)`. При установке фреймворка как чистого wheel-пакета без `process/schemas` в site-packages потребуется упаковка schemas через package_data (будет детальнее проверено в A06-02).

## Handoff

- **Результат**: Модульные границы, SSOT для схем/статусов/версий и диагностические контракты подтверждены.
- **Готовность к переходу**: Разрешён переход к карточке [A06-02](packets/A06-02.md) — «Проверить установку, пакет и pin/lock/hash».
