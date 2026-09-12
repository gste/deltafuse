# QF-003 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `2d35917` (QF-002)
- **Инструменты:** Python .venv 3.12.14 (uv), pytest, git, Windows 10.0.26200

## Реализация (`scripts/qualify.py`)

- Sandbox — git-репозиторий: `init_sandbox_git` (init, локальный
  qualification-bot user, минимальный .gitignore, начальный bookkeeping-коммит);
  `drive_worker` инициализирует/переиспользует репозиторий сам (идемпотентно).
- `inventory(sandbox, expected_head)`: `git status --porcelain -uall` →
  упорядоченный dict; tamper-guard: HEAD ≠ bookkeeping-SHA →
  `QualificationError("inventory_tampered...")`.
- `SandboxIO.inventory_fn` (injectable): до/после каждой shell-команды
  снимается inventory; diff приписывается shell-событию в `paths_written`.
- Разделение read/write телеметрии: в leash идут только `paths_written`
  стадии (`stage_writes`), reads — только в T5.
- Advance детектируется по argv (`deltafuse advance`), не по подстроке.
  Порядок на границе стадии (с обоснованием из инструкции, зафиксирован в
  docstring `drive_worker`): Core leash ЗАРАНЕЕ advance с write-set'ом
  закрываемой стадии (envelope времени записи) → advance → сверка
  журнал/инвентарь (`unjournaled_change`, `.deltafuse/**` исключён как
  Core-owned) → bookkeeping-коммит, очистка write-set.
- `_core_leash_violations` возвращает (count, details); per-run report
  содержит `t7_breakdown` (write_denied, leash_violations,
  unjournaled_change, inventory_tampered) и `stage_leash`;
  `envelope_violations` = сумма компонентов (формула 2.5); `apply_thresholds`
  падает по T7 при любом ненулевом компоненте.

## Red-фаза (до реализации)

```
FAILED test_shell_created_file_outside_envelope_fails_t7
FAILED test_reads_never_sent_to_leash - AssertionError
FAILED test_past_stage_files_not_rechecked_by_new_envelope
FAILED test_leash_runs_per_advance_with_stage_writeset
FAILED test_inventory_tamper_detected - AttributeError: init_sandbox_git
FAILED test_unjournaled_change_detected - KeyError: 't7_breakdown'
```

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests
1 failed, 399 passed, 1 skipped in 222.82s
```

Единственный failed — известный дефект QF-005 (`python` из PATH без pytest),
падал до начала работ, в пакет не входит.

Smoke:
```
pwsh -File tests/smoke-test.ps1   # rc=0
bash tests/smoke-test.sh          # rc=0
```

## Acceptance

- [x] Shell-команда, создающая файл вне envelope (`git diff --output=leak.txt`),
      обнаруживается inventory-diff и валит T7 через Core leash
      (`test_shell_created_file_outside_envelope_fails_t7`).
- [x] Чтение разрешённого файла не попадает в leash;
      правка файла прошлой стадии не перепроверяется новым envelope
      (`test_reads_never_sent_to_leash`,
      `test_past_stage_files_not_rechecked_by_new_envelope`).
- [x] `unjournaled_change`-детект работает
      (`test_unjournaled_change_detected`).
- [x] Leash на каждой границе стадии, write-set стадии, до advance
      (`test_leash_runs_per_advance_with_stage_writeset`); tamper-guard
      (`test_inventory_tamper_detected`).
- [x] T7 имеет измеримый источник: `t7_breakdown` + `stage_leash` в report.
- [x] Полный suite (кроме известного QF-005) и оба smoke зелёные.

## Замечания

- Полный pytest/smoke загрязняют tracked `bench/builds/*-build-manifest.json`
  (дефект QF-010); файл восстановлен до коммита.
- Отклонение от буквы плана («leash после перехода») — по обоснованию самой
  инструкции §2.4: leash после advance давал бы ложную классификацию;
  зафиксировано в docstring `drive_worker`.
