# QF-004 — результат исполнения

- **Статус:** выполнено (с отклонением по venv, см. «Отклонения»)
- **Базовый commit:** `dee4eea` (QF-003)
- **Инструменты:** Python .venv 3.12.14 (uv), pytest, git 2.45.1, Windows 10.0.26200

## Реализация

- `parse_shell_command(command) -> (argv, reason)` — точная политика
  профилей: `deltafuse` (флаги только `--json`, `--gate <имя>` для advance,
  `--human` для next), `pytest` (фиксированный набор флагов + позиционные
  test-id; `-k`/`-m`/`--co` разрешены), `python` только как
  `python -m pytest` (правила pytest), `git status|diff|log|show` **без
  опций вообще**, позиционный только точный `HEAD`. Глобально запрещены:
  `@`-response files, `--`, UNC (`\\`, `//`), absolute/`X:` пути, traversal,
  `%ENV%`. Причина отказа журналируется в ToolEvent (для QF-006).
  `parse_shell_argv` сохранён как compat-обёртка.
- `scripts/qualify_staging.py` — `StagingRoot`: base/venv/work,
  `new_workdir` (копия sandbox-репозитория), `collect_workdir`,
  `env()` (минимальное окружение: контролируемый интерпретатор + git на
  PATH, без `PYTHON*` и framework-ссылок), `interpreter()`,
  `escape_walker()` (файлы в staging вне work/venv → `staging_escape`),
  `_build_venv` (wheel+pytest, выполняется явно на host квалификации).
- `SandboxIO`: `exec_env`, `interpreter` (токен `python` исполняется
  контролируемым интерпретатором — git-bash/subprocess под uv-venv терял
  контекст venv через PATH), `escape_check_fn`; `shell` выполняет команды с
  `env=exec_env`, walker после каждой команды; `staging_escape` — счётчик и
  компонент `t7_breakdown` (T7).
- `drive_worker(..., staging=...)`; `run_case`: staging на кампанию,
  work-копия per run, обратный перенос перед scoring.
- `backlog/product/v3/qualification-threat-model.md` — активы, L1/L2,
  платформенные гарантии Windows/POSIX; ссылка в docstring `drive_worker`.

## Red-фаза (до реализации)

```
FAILED test_allowed_shell_commands_still_run - ModuleNotFoundError qualify_staging
FAILED test_shell_created_file_outside_envelope_fails_t7
FAILED test_git_output_option_rejected            (git diff --output создавал файл)
FAILED test_git_any_option_rejected               (--oneline/--porcelain проходили)
FAILED test_pytest_plugin_and_config_options_rejected
FAILED test_pytest_allowed_subset_still_runs
FAILED test_deltafuse_flag_policy - AttributeError: parse_shell_command
FAILED test_response_file_and_dashdash_rejected
FAILED test_unc_and_network_paths_rejected - AttributeError
FAILED tests/integration/... - ModuleNotFoundError: qualify_staging
```

Не-Red исключение: `test_symlink_and_junction_escape_rejected` проходил и до
реализации — resolve-guard `_resolve` уже отклонял переходы по junction
(зафиксировано как ранее существовавшая защита, тест оставлен как регрессия).

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests
410 passed, 1 skipped, 54 warnings in 194.35s
```

Полный suite зелёный впервые с начала работ: `test_allowed_shell_commands_still_run`
зелёный через staging-окружение (что и предписано шагом 3 инструкции QF-004).

Smoke: `pwsh tests/smoke-test.ps1` rc=0; `bash tests/smoke-test.sh` rc=0.

## Acceptance

- [x] Матрица обходов (git output/options, pytest plugin/config/ini/import,
      response files, `--`, UNC/сетевые/absolute, traversal) — RED→GREEN.
- [x] Junction/symlink escape — отклоняется (регрессионный тест).
- [x] Integration: разрешённый `python -m pytest` в staging не находит judge
      pack (pack физически отсутствует).
- [x] Walker детектирует файл, появившийся в staging вне work
      (`staging_escape` → T7), в т.ч. сквозной тест через `drive_worker`.
- [x] Threat model написан и привязан к runner.
- [x] Полный suite + оба smoke зелёные на Windows; POSIX-ветка (symlink)
      покрыта `sys.platform`-гейтом.

## Отклонения

- venv в staging по умолчанию не собирается (`build_venv=False`): сборка
  требует pip wheel + индекс для pytest; механизм реализован
  (`_build_venv`) и выполняется явно на host квалификации. Интерпретатор
  по умолчанию = интерпретатор runner'а (`StagingRoot.interpreter`),
  точная нормализация окружения — следующий пакет QF-005 (как и
  предусматривает инструкция: «детали окружения доделает QF-005»).
- QF-003 тест создания shell-файла переведён с `git diff --output=leak.txt`
  (теперь запрещён) на Worker-authored `python -m pytest leaky_test.py` —
  вариант, прямо названный в инструкции QF-003.
