# Qualification fixes — инструкции исполнителя

Пошаговые инструкции для исправления дефектов из
[qualification-fix-plan.md](../qualification-fix-plan.md). Каждому дефекту
QF-001…QF-012 соответствует отдельная папка с самодостаточной инструкцией
`INSTRUCTION.md`. Инструкции написаны для автономного агента-исполнителя,
который не имеет контекста этой сессии: в каждой папке есть точные координаты
дефекта в коде, нормативное поведение, Red-тесты, план реализации, acceptance
и список evidence.

## Порядок исполнения

Пакеты выполняются строго по номерам; зависимости зафиксированы в заголовке
каждой инструкции и повторены здесь:

| # | Папка | Приоритет | Зависимости | Commit message |
|---|---|---|---|---|
| 1 | [QF-001-fail-closed-write-envelope](QF-001-fail-closed-write-envelope/INSTRUCTION.md) | P0 | — | `qualify: fail closed on missing write envelope` |
| 2 | [QF-002-call-file-measurement](QF-002-call-file-measurement/INSTRUCTION.md) | P0 | QF-001 | `qualify: measure files per worker call` |
| 3 | [QF-003-stage-leash-inventory](QF-003-stage-leash-inventory/INSTRUCTION.md) | P0 | QF-001, QF-002 | `qualify: enforce leash against stage changes` |
| 4 | [QF-004-execution-boundary](QF-004-execution-boundary/INSTRUCTION.md) | P0 | QF-003 | `qualify: isolate worker command execution` |
| 5 | [QF-005-interpreter-and-env](QF-005-interpreter-and-env/INSTRUCTION.md) | P0 | QF-004 | `qualify: pin interpreter and environment` |
| 6 | [QF-006-literal-t4-t6-t8](QF-006-literal-t4-t6-t8/INSTRUCTION.md) | P0 | QF-002–QF-004 | `qualify: make T4 T6 T8 evidence literal` |
| 7 | [QF-007-host-attestation](QF-007-host-attestation/INSTRUCTION.md) | P1 | QF-006 | `qualify: attest reference host` |
| 8 | [QF-008-report-schema-and-failures](QF-008-report-schema-and-failures/INSTRUCTION.md) | P1 | QF-006 | `qualify: validate reports and preserve failures` |
| 9 | [QF-009-atomic-asset-sync](QF-009-atomic-asset-sync/INSTRUCTION.md) | P1 | — | `assets: make bundle replacement atomic` |
| 10 | [QF-010-wheel-evidence-separation](QF-010-wheel-evidence-separation/INSTRUCTION.md) | P1 | — | `wheel: separate smoke from release evidence` |
| 11 | [QF-011-engineering-requalification](QF-011-engineering-requalification/INSTRUCTION.md) | P1 | QF-001–QF-010 | `release: record clean engineering qualification` |
| 12 | [QF-012-reference-qualification](QF-012-reference-qualification/INSTRUCTION.md) | P1 | QF-011 + LM Studio host | `release: record reference qualification` |

QF-009 и QF-010 не зависят от qualify-пакетов и могут выполняться параллельно
с очередью P0, но QF-011 требует их завершения.

## Общие правила для всех пакетов

1. **Один пакет — один commit.** Commit message зафиксирован в инструкции.
   В commit входят: код, тесты, документация и `RESULT.md` текущего пакета.
   Никаких смешанных пакетов.
2. **Red → Green → регрессия.** Сначала пишутся и фиксируются Red-тесты
   (падают на текущем коде), затем реализация, затем полный прогон регрессии.
   Red-тесты — часть того же commit; в `RESULT.md` приводится вывод pytest
   для Red-фазы (до реализации) и Green-фазы (после).
3. **Evidence обязателен.** По завершении пакета исполнитель создаёт
   `RESULT.md` в папке пакета: точные команды, версии инструментов, counts,
   SHA и сохранённые артефакты. Следующий пакет нельзя начинать, пока
   acceptance предыдущего не подтверждён evidence, а не описанием агента.
4. **Запреты.** Не ослаблять пороги T1–T8 и константы `ABSOLUTE`; не менять
   `thresholds.md` без maintainer Decision; не запускать `git push` и
   деструктивные git-команды; не мержить в `master`; не коммитить секреты и
   абсолютные пути окружения; не синтезировать результаты reference runs.
5. **Статус программы.** До полного успеха QF-011 статус остаётся
   `engineering-failed`; DF3-009 остаётся `blocked` до QF-012. Отсутствие
   LM Studio не мешает QF-001–QF-011.
6. **Базовый commit кода.** Все ссылки на строки кода в инструкциях даны для
   commit `bb02820` (ветка `feature/2026-09-11-audit`). Если строки сместились
   из-за предыдущих пакетов, ориентироваться на имена функций и цитаты кода.

## Сквозные конвенции

Эти решения зафиксированы заранее, чтобы исполнители разных пакетов не
расходились. Первый пакет, который вводит конвенцию, реализует её; следующие —
переиспользуют.

### Типизированный журнал tool events (вводит QF-002)

`SandboxIO` ведёт список событий `events: list[ToolEvent]` вместо приращивания
счётчиков. Каждое событие закрывается **после** выполнения действия:

```python
@dataclass
class ToolEvent:
    call_index: int              # 1-based номер Worker-вызова
    seq: int                     # сквозной номер действия
    tool: str                    # "read" | "write" | "shell" | "unknown"
    outcome: str                 # "ok" | "error" | "rejected" | ...
    paths_read: list[str]        # фактически прочитанные относительные пути
    paths_written: list[str]     # фактически записанные относительные пути
    command: str | None          # argv для shell
    exit_code: int | None
    envelope_globs: list[str] | None   # envelope.write, действовавший при записи (QF-003)
```

Производные метрики (T5, T6, T7) вычисляются из журнала, а не из счётчиков.
QF-003 добавляет к событиям inventory-diff вокруг shell-команд; QF-006
классифицирует события по T6/T7.

### Provenance сообщений Worker (вводит QF-006)

`drive_worker` хранит параллельно `messages` список записей provenance:
`origin` = `system` | `framework` | `product` (framework = system prompt,
Core-ответы и протокольные строки runner; product = тела прочитанных файлов,
вывод pytest). Полный вход вызова измеряется host usage; framework-часть —
отдельно по provenance-тегам (см. INSTRUCTION QF-006).

### Provenance полей manifest (вводит QF-007)

Каждое неотъемлемое поле manifest/report, влияющее на verdict, помечено
`provenance: measured | declared | derived` и `method`/`basis`. Константа
никогда не публикуется как измерение.

### Схемы артефактов qualification (вводит QF-008)

JSON Schema draft 2020-12: `scripts/schemas/run-manifest.schema.json` и
`scripts/schemas/run-report.schema.json`; валидация `jsonschema`
(уже в requirements-dev.txt) перед каждой атомарной записью.

## Команды проверки (общие)

```bash
# полный юнит/интеграционный suite
.venv/Scripts/python.exe -m pytest tests -q

# smoke (обязательны для пакетов, меняющих scripts/ или tests/)
pwsh -File tests/smoke-test.ps1        # PowerShell
bash tests/smoke-test.sh               # Git Bash / POSIX

# drift bundle (только чтение)
.venv/Scripts/python.exe scripts/sync_assets.py --check

# чистота дерева до/после любого пакета
git status --porcelain
```
