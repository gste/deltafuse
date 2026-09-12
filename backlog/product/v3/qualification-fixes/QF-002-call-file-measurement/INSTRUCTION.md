# QF-002 — корректное измерение T5 по каждому вызову

- **Приоритет:** P0
- **Зависимости:** QF-001 (EnvelopeState уже в коде)
- **Commit:** `qualify: measure files per worker call`
- **Исходный дефект:** [qualification-fix-plan.md, QF-002](../../qualification-fix-plan.md)
- **Код на момент написания:** commit `bb02820` (после QF-001 строки
  `drive_worker` сместились — ориентироваться на имена функций и цитаты)

Исполнитель: читай [README.md](../README.md) до начала работы. Особо важна
конвенция «Типизированный журнал tool events» — её вводит этот пакет.

## 1. Дефект

`drive_worker` фиксирует измерение `call_unique_files` **до** выполнения tool
action, а `io.begin_call()` сбрасывает счётчик в начале вызова. Реальное
чтение, сделанное последним действием вызова, в измерение не попадает:

```python
# scripts/qualify.py, drive_worker (было на bb02820):
for _ in range(MAX_WORKER_TURNS):
    io.begin_call()                       # call_files = set()
    io.write_globs = _core_envelope(...)
    turn = worker_turn(...)               # ответ модели
    ...
    calls.append({
        ...
        "unique_files": io.call_unique_files,   # ИЗМЕРЕНО ДО action
        ...
    })
    messages.append({"role": "assistant", ...})
    action = parse_action(turn["content"])
    if tool == "read_file":               # action ВЫПОЛНЯЕТСЯ ПОСЛЕ записи
        result = io.read_file(...)
    ...
```

Следствия:

- T5 (`max_unique_files`) для вызова, завершившегося чтением, равен `0`,
  хотя файл реально прочитан (подтверждено прямым probe в независимой
  проверке №3: реальное чтение даёт `unique_files: 0`).
- Смешение «сколько файлов затронул вызов» с накопительными множествами за
  весь run (`io.unique_files`).
- Нет журнала действий: метрики — это счётчики, из которых невозможно
  восстановить, что происходило (это же блокирует QF-003 и QF-006).

## 2. Нормативное поведение

1. Вводится типизированный журнал `ToolEvent` (см. README, конвенция).
   Событие создаётся **после** выполнения действия и содержит фактические
   `paths_read` / `paths_written` (относительные posix-пути внутри sandbox).
2. Порядок измерения вызова:
   1. `begin_call()` — открывает новый `call_index`;
   2. `worker_turn(...)` — ответ модели;
   3. выполняется tool action (read/write/shell), событие журнала закрывается
      с фактическими путями;
   4. **только теперь** измерение вызова фиксируется: `unique_files` вызова =
      число уникальных путей в `paths_read ∪ paths_written` событий этого
      `call_index`.
3. Вызов без tool action (`tool == "done"` или неизвестный tool) имеет
   `unique_files = 0` — это корректное измерение, а не пропуск.
4. Повторное чтение/запись того же пути внутри одного вызова не увеличивает
   `unique_files` (множество, не счётчик).
5. `max_unique_files` = максимум по всем вызовам run, включая последний
   вызов перед `done`.
6. Shell-команды: событие записывается с `command` (argv), `exit_code` и
   `paths_read`/`paths_written` из известных напрямую эффектов. Полная
   атрибуция путей, созданных shell-командой (inventory-diff), — территория
   QF-003; здесь достаточно, чтобы shell-событие существовало в журнале и
   не ломало измерение (пустые списки путей допустимы).

## 3. План работ

### Шаг 1 — Red-тесты (`tests/unit/test_qualify.py`)

Имена обязательны:

- `test_last_action_read_counts_in_unique_files` — сквозной тест
  `drive_worker` на временном sandbox (можно `init_bench_product` в tmp_path
  или минимальный ручной sandbox с `.deltafuse/bench.yaml`; см. существующий
  `test_score_product_report_satisfies_thresholds_shape` и фикстуру
  `repo_root`): стаб `worker_turn` возвращает два вызова —
  (1) `{"tool": "read_file", "path": "docs/spec/core.md"}` (файл создать
  заранее), (2) `{"tool": "done"}`. Метрика вызова 1 обязана содержать
  `unique_files: 1`; `max_unique_files == 1`.
- `test_repeated_path_same_call_not_double_counted` — один вызов читает
  `a.md` дважды (два действия невозможны в текущем протоколе — тогда один
  вызов: `read a.md`; второй вызов: `read a.md` + `read b.md` через
  последовательные вызовы). Цель: `unique_files` второго вызова = 2, не 3.
  Если протокол не позволяет несколько действий в одном вызове, проверить
  инвариант напрямую на `SandboxIO`: события одного `call_index` с
  повторяющимся путём дают размер множества 1.
- `test_multiple_actions_across_calls_accumulate_per_call` — три вызова с
  разными наборами путей; каждый вызов измеряется своим множеством, run-максимум
  равен максимуму множеств, а не сумме.
- `test_tool_event_journal_shape` — после прогона журнал содержит события с
  обязательными полями (`call_index`, `seq`, `tool`, `outcome`,
  `paths_read`, `paths_written`), монотонными `seq` и корректными
  `call_index`.

Все новые тесты обязаны падать до реализации (Red-вывод в RESULT.md).

### Шаг 2 — Реализация (`scripts/qualify.py`)

1. `@dataclass ToolEvent` — точно по конвенции README (включая
   `envelope_globs: list[str] | None = None` — поле появится в QF-003,
   но завести его сейчас дешевле, чем менять сигнатуру позже).
2. `SandboxIO`:
   - `self.events: list[ToolEvent]`, `self._seq`, `self._call_index`;
   - `begin_call()` инкрементирует `call_index`;
   - `read_file`/`write_file` после фактического чтения/записи добавляют
     событие с фактическим путём (успешно прочитанный путь — в
     `paths_read`; записанный — в `paths_written`; отказ — событие с
     `outcome="error"`/`"rejected"` и причиной, путь включается как
     запрошенный — классификация нарушений по T6/T7 будет в QF-006, сейчас
     счётчики `hallucinated_paths`/`envelope_violations` сохраняются как есть);
   - `shell` добавляет событие с `command` (argv), `exit_code`; пути —
     пустые списки до QF-003;
   - удалить `call_files`/`call_unique_files`-механику счётчиков; добавить
     `def call_paths(self, call_index) -> set[str]` — объединение путей
     событий вызова.
3. `drive_worker`:
   - вызвать `io.begin_call()` как сейчас;
   - **перенести** `calls.append({...})` на позицию ПОСЛЕ выполнения tool
     action (после `messages.append({"role": "user", "content": result})`);
   - `"unique_files": len(io.call_paths(io.call_index))`;
   - в per-run метрики добавить `"tool_events": [asdict(e) for e in io.events]`
     (сериализуется в report per-run; компактно: без тел файлов).
4. `run_case`: пробросить `tool_events` в `per_run` (поле `calls` остаётся,
   дополняется/дублируется корректным `unique_files`).

### Шаг 3 — Регрессия

- `pytest tests -q` — 0 failed. Особо: `test_envelope_gated_write_rejected`
  (QF-001-версия), `test_adversarial_shell_commands_are_rejected`,
  `test_synthetic_campaign_with_failure_is_nonzero_and_saves_all`
  (fake_run_case не затронут, но форма per_run не должна ломать main()).
- Smoke-тесты не требуются (scripts/qualify.py не входит в smoke), но
  прогнать полный pytest обязательно.

## 4. Границы и запреты

- Не менять семантику T5 в `ABSOLUTE` (порог 24) и в `apply_thresholds`
  (граница/`unmeasured` уже корректны — чинится измерение, не оценка).
- Не вводить inventory-diff для shell (QF-003) и не классифицировать
  нарушения T6/T7 из журнала (QF-006) — только заготовить события.
- Не менять протокол Worker (JSON-действия) и system prompt.

## 5. Acceptance

- [ ] Worker читает один файл последним действием вызова → в отчёте вызова
      `unique_files: 1` (сквозной Red-тест зелёный).
- [ ] Повтор того же пути не увеличивает значение (тест есть).
- [ ] Несколько вызовов: каждый измеряется своим множеством; run-максимум —
      по вызовам (тест есть).
- [ ] Журнал `tool_events` присутствует в метриках run и имеет заданную
      форму (тест есть).
- [ ] Полный suite зелёный.

## 6. Evidence для RESULT.md

1. Red-вывод новых тестов до реализации.
2. Green-вывод полного suite (counts).
3. `git rev-parse HEAD` до/после, состав commit.

## 7. Commit

Один commit: `qualify: measure files per worker call`.
Состав: `scripts/qualify.py`, `tests/unit/test_qualify.py`, `RESULT.md`
этой папки.
