# QF-021 — результат исполнения

- **Статус:** выполнено
- **Базовый commit (parent):** `0efd5a8ed47e927f21a4e8f6fc82e190ebc83a90`
  — параллельный commit `bench: add Java calibration stream seed`
  (bench/incubator/**, к qualify-кодовой базе отношения не имеет) поверх
  `f5bf7ee…` (QF-020); ветка `feature/2026-09-11-audit`
- **Итоговый commit:** тот, в котором лежит этот файл (child of base)
- **Инструменты:** Python 3.12.14 (.venv, CPython), pytest 9.1.1, Windows
  10.0.26200 (win32)
- **Red evidence:** `tests/unit/test_qualify_evidence.py` на базовом commit —
  коллекция падала `ModuleNotFoundError: No module named 'qualify_evidence'`:
  независимого disk-evaluator не существовало, schema+semantic validation
  принимали сохранённый `pass` с неизвестной стадией, `context_peak_tokens=99999`,
  hallucinated/envelope > 0, а totals/verdict/executor никогда не
  пересчитывались из disk artifacts.

## Реализация

- **`scripts/qualify_evidence.py`** (новый, pure: без импортов фреймворка и
  runner state) — ЕДИНСТВЕННАЯ реализация T1–T8:
  - `recompute(report, thresholds, executor, enforce_stored)` →
    `(pass_verdict, threshold_failures, problems)`; `evaluate_artifact(...)`
    — audit-обёртка `(consistent_and_pass, all_reasons)`;
  - пересчёт из первичных disk fields: T1 — checks по стадиям; T2 — точное
    множество/порядок/статусы `LIFECYCLE`; T3 — сумма и per-stage retries;
    T4 — max input/framework tokens по calls + method `host-tokenize` на
    каждый вызов + framework chars; T5 — per-call unique paths,
    ВОССТАНАВЛИВАЕМЫЕ из tool events (удаление/дублирование события
    обнаружимо); T6 — `classify_violations` по typed journal;
    T7 — breakdown (write_denied/leash-receipts/unjournaled/tampered/
    escape/execution_policy) с восстановлением leash-суммы по `stage_leash`
    и сверкой write_denied с классификацией событий; T8 — встроенные
    `defense_checks` с обязательными receipt-detail;
  - сохранённые `totals`, `process`, `correctness`, `threshold_failures`,
    `verdict` НЕ доверяются: пересчитываются и требуют точного совпадения
    (problems); NaN/inf в любой точке артефакта, boolean-as-number,
    дубликаты стадий/событий, события вне диапазона calls — всегда отказ;
  - embedded identity: каждый report несёт `thresholds` (source/revision/
    absolute snapshot) и `executor_kind`; расхождение с манифестом — отказ;
  - `case_medians`/`evaluate_case_medians` — единственный источник медиан
    (runtime и audit).
- **Runner** (`scripts/qualify.py`): report строится ДО вердикта; verdict и
  `threshold_failures` ставятся из `recompute` того же артефакта, который
  пишется на диск (runtime и audit — одна реализация, byte-for-byte);
  `apply_thresholds` — тонкий live-адаптер над тем же evaluator;
  classification/lifecycle-функции перенесены в evaluator (re-export).
- **`qualify_semantic.semantic_validate_manifest`**: каждый report
  перезагружается и прогоняется через evaluator (enforce_stored) против
  threshold-блока и executor-блока манифеста; медианы и median_failures
  пересчитываются из disk reports и требуют точного совпадения; release
  `pass` требует measured boundary probe (declared-only граница
  блокируется), не-isolated кампания по-прежнему капится `non-release`.
- **Схема** `run-report.schema.json`: добавлены `defense_checks`,
  `thresholds` (snapshot), `executor_kind`, `points` (earned/max — первичный
  источник correctness); correctness пересчитывается как
  `round(100*earned/max, 1)` и сверяется.

## Проверки

| # | Команда | Результат |
|---|---|---|
| 1 | Red: `pytest tests/unit/test_qualify_evidence.py` в worktree `f5bf7ee` | `ModuleNotFoundError: No module named 'qualify_evidence'` — evaluator отсутствовал |
| 2 | `pytest tests/unit/test_qualify_evidence.py` после реализации | 38 passed, exit 0 |
| 3 | Полный qualification-набор (unit + integration qualify/sync/schemas) | 0 failed |
| 4 | `pytest tests -q -p no:cacheprovider --junitxml=…` | tests=616, failures=0, errors=0, **skipped=7**, exit 0 (609 passed) |

Mutation-матрица: ранее проходивший мутант-`pass` (bogus stage + context
99999 + hallucinated 5 + envelope 4) отклоняется с точными причинами T2/T4/
T6/T7; по одной консистентной мутации на каждое первичное поле T1–T8
(порог нарушен — verdict обязан стать fail); занижение totals/очистка
threshold_failures/подмена verdict/чужой revision/чужой executor_kind —
problems; удаление/дублирование события/стадии — problems (в т.ч. через
восстановление unique-наборов путей); NaN/inf/bool-as-number — отказ.
Ни один `pass` нельзя получить изменением только производных полей.

Skips (7) — без изменений: 4 live boundary QF-020, 2 live command-container
QF-019, 1 PBT. Дерево чистое после commit; tracked evidence не
перезаписывался.
