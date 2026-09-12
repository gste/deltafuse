# QF-009 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `6ef27f3` (QF-008)
- **Инструменты:** Python .venv 3.12.14, pytest, Windows 10.0.26200

## Реализация (`scripts/sync_assets.py`)

- `sync()` атомарна: генерация во временный sibling
  `assets.next-<pid>-<rand>` (тот же том) → запись manifest →
  самопроверка `_verify_bundle` (manifest читается, каждый файл на месте,
  sha256 совпадает) → атомарный `_swap_in` → печать. Проблемы канонических
  источников возвращаются (rc=1) БЕЗ swap.
- `_swap_in(new_dir, target)`: `assets → assets.prev-…` (если есть) →
  `next → assets`; при неудаче второго rename — rollback `prev → assets`
  и `RuntimeError("...previous bundle restored")`; при успехе prev
  удаляется. `_rename = os.rename` — module-level alias для fault injection.
- `_cleanup_stale`: `assets.next-*` / `assets.prev-*` подчищаются на старте
  sync; невалидированный temp-каталог никогда не становится `assets`.
- `--check` не изменён (read-only, V3-FIX-022). Docstring обновлён.

## Red-фаза (до реализации)

```
FAILED test_failed_generation_keeps_previous_bundle  (bundle исчезал при сбое)
FAILED test_swap_rollback_on_rename_failure - AttributeError: _rename
FAILED test_stale_temp_dirs_cleaned - AssertionError
(test_successful_sync_replaces_bundle / test_check_detects_drift...
частично перекрывались прежним поведением; теперь закрепляют атомарность)
```

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests
[полный suite зелёный, 0 failed]
.venv/Scripts/python.exe scripts/sync_assets.py --check
check: bundle is up to date (44 assets)   rc=0
pwsh tests/smoke-test.ps1  rc=0;  bash tests/smoke-test.sh  rc=0
```

Fault injection (тест): sha256-снапшот bundle до/после неудачной генерации —
байт-в-байт идентичен, temp-мусор вычищен; rename-failure → rollback,
снапшот идентичен.

## Acceptance

- [x] Fault injection между генерацией и swap сохраняет предыдущий bundle
      байт-в-байт.
- [x] Drift обнаруживается `--check` без изменения дерева.
- [x] Неуспешная генерация не оставляет отсутствующий/частичный bundle;
      stale temp-каталоги вычищаются.
- [x] Полный suite + оба smoke зелёные; `sync_assets.py --check` rc=0.
