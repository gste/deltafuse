# QF-001 — результат исполнения

- **Статус:** выполнено (acceptance выполнен, кроме одного пункта, см. «Отклонения»)
- **Базовый commit:** `121e64651428343b3966d6a79f1c3d283ed12ff1` (после коммита инструкций)
- **Инструменты:** Python `.venv/Scripts/python.exe` (3.12.14, uv-managed), pytest, Windows 10.0.26200, Git Bash

## Реализация

- `scripts/qualify.py`: введён `EnvelopeState(status, globs, detail)`;
  `_core_envelope` классифицирует ошибки (exception / non-zero exit / invalid
  JSON / не-объект) как `status="error"` и больше никогда не возвращает `[]`
  как ответ на ошибку; `SandboxIO.write_envelope` заменяет `write_globs`,
  fail-closed при `None`/`error`/`ok`-empty (при пустом envelope разрешены
  только exempt-пути Core); отдельный счётчик `envelope_errors`;
  `drive_worker` при `status="error"` прерывает run и возвращает
  `envelope_error=<detail>`; `apply_thresholds` добавляет
  `T7 envelope_unavailable=<detail>` при наличии `envelope_error`.
- Заготовка QF-003: `SandboxIO.last_write_envelope_globs` — globs,
  авторизовавшие последнюю успешную запись.

## Red-фаза (до реализации)

```
.venv/Scripts/python.exe -m pytest tests/unit/test_qualify.py -q
FAILED tests/unit/test_qualify.py::test_sandbox_io_rejects_escapes - AttributeError
FAILED tests/unit/test_qualify.py::test_allowed_shell_commands_still_run - AssertionError
FAILED tests/unit/test_qualify.py::test_envelope_gated_write_rejected - AttributeError
FAILED tests/unit/test_qualify.py::test_write_envelope_ok_empty_denies_product_writes
FAILED tests/unit/test_qualify.py::test_write_envelope_error_denies_and_flags
FAILED tests/unit/test_qualify.py::test_write_envelope_missing_is_fail_closed
FAILED tests/unit/test_qualify.py::test_core_envelope_malformed_json_is_error
FAILED tests/unit/test_qualify.py::test_core_envelope_nonzero_exit_is_error
FAILED tests/unit/test_qualify.py::test_core_envelope_ok_responses - AttributeError
FAILED/tests/unit/test_qualify.py::test_drive_worker_fails_closed_when_envelope_unavailable
```

Все новые тесты падали на нереализованном API (`AttributeError:
EnvelopeState` и поведение «пустой/ошибочный envelope разрешает запись»).

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests/unit/test_qualify.py
# 1 failed, 40 passed  (единственный failed — test_allowed_shell_commands_still_run, см. ниже)

.venv/Scripts/python.exe -m pytest tests
# 1 failed, 389 passed, 1 skipped in 195.18s
```

Полный suite: единственный failed — `test_allowed_shell_commands_still_run`,
это **заранее задокументированный дефект QF-005** (разрешённый
`python -m pytest` берёт `python` из PATH, где нет pytest: uv cpython 3.12.14
без pytest). Он падал и до этого пакета (независимый прогон в плане:
`1 failed, 382 passed, 1 skipped`); чинить его в QF-001 запрещено правилом
«никаких смешанных пакетов». После QF-005 ожидается зелёный suite.

## Smoke

```
pwsh -File tests/smoke-test.ps1   # Smoke test passed successfully!
bash tests/smoke-test.sh          # Smoke test passed successfully!
```

Замечание: прогон smoke загрязнил отслеживаемый
`bench/builds/deltafuse-3.0.0-py3-none-any-build-manifest.json` — известный
дефект QF-010; файл восстановлен (`git checkout --`) до коммита, в пакет не
входит.

## Acceptance

- [x] Разрешены записи только в пути текущего Core envelope или exempt-пути.
- [x] `ok-empty` envelope отклоняет product-записи
      (`test_write_envelope_ok_empty_denies_product_writes`).
- [x] Ошибки Core (malformed JSON / non-zero exit / исключение) дают отказ
      записи, classified detail и fail по T7 (по тесту на ситуацию;
      timeout в in-process CLI недостижим и покрыт веткой exception).
- [x] Run с недоступным envelope даёт T7 failure
      (`test_drive_worker_fails_closed_when_envelope_unavailable`); exit code
      кампании ненулевой, т.к. verdict run = fail.
- [x] Все Red-тесты зелёные; полный suite зелёный **за исключением
      предварительно падающего QF-005 теста** (см. «Отклонения»); smoke зелёные.
- [x] `RESULT.md` заполнен.
