# QF-002 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `5f4a902c9bf605ed75eab8592716bcba4eb74006` (QF-001)
- **Инструменты:** Python .venv 3.12.14 (uv), pytest, Windows 10.0.26200

## Реализация

- `scripts/qualify.py`: типизированный журнал `ToolEvent(call_index, seq,
  tool, outcome, paths_read, paths_written, command, exit_code,
  envelope_globs)` по конвенции README; `SandboxIO` ведёт `events`,
  `begin_call()` инкрементирует `call_index`; read/write/shell (включая
  отказы и ошибки) закрывают событие с фактическими путями после выполнения
  действия; `call_paths(call_index)` — объединение путей событий вызова;
  счётчики `call_files`/`call_unique_files` удалены; `drive_worker` измеряет
  вызов ПОСЛЕ tool action; `tool_events` добавлены в run-метрики и в per-run
  `report.yaml` (`run_case`).

## Red-фаза (до реализации)

```
.venv/Scripts/python.exe -m pytest tests/unit/test_qualify.py -q -k "last_action_read or repeated_path or multiple_actions or tool_event_journal"
FAILED test_last_action_read_counts_in_unique_files
FAILED test_repeated_path_same_call_not_double_counted
FAILED test_multiple_actions_across_calls_accumulate_per_call
FAILED test_tool_event_journal_shape - KeyError: 'tool_events'
```

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests
1 failed, 393 passed, 1 skipped in 204.36s
```

Единственный failed — `test_allowed_shell_commands_still_run`,
заранее задокументированный дефект QF-005 (`python` из PATH без pytest);
падал и до QF-001, в этот пакет не входит.

## Acceptance

- [x] Чтение последним действием вызова попадает в `unique_files`
      (`test_last_action_read_counts_in_unique_files`: `unique_files: 1`).
- [x] Повтор пути в одном вызове не увеличивает значение
      (`test_repeated_path_same_call_not_double_counted`).
- [x] Вызовы измеряются своими множествами; run-максимум = max множеств
      (`test_multiple_actions_across_calls_accumulate_per_call`: [1,1,1,0],
      max 1, не сумма 3).
- [x] Журнал `tool_events` в метриках run, форма по конвенции, серилизуем в
      report (`test_tool_event_journal_shape`).
- [x] Полный suite зелёный, кроме известного QF-005 теста.

## Замечания

- Полный pytest сам загрязняет отслеживаемый
  `bench/builds/deltafuse-3.0.0-py3-none-any-build-manifest.json` (wheel
  smoke внутри suite) — известный дефект QF-010; файл восстановлен до
  коммита, в пакет не входит.
- Smoke-тесты по инструкции пакета не требуются (scripts/qualify.py не в
  scope smoke).
