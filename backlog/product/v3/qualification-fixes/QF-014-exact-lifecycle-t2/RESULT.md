# QF-014 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `2f26af1` (QF-013)
- **Red evidence:** `tests/unit/test_qualify_lifecycle.py` — до реализации:
  collection error (`deltafuse.core.lifecycle` отсутствует,
  `check_exact_lifecycle` не существует); старый T2 (`completed < 7`)
  принимал 8 стадий и 7 произвольных.

## Реализация

- **Единый контракт**: `src/deltafuse/core/lifecycle.py` — канонический
  ordered tuple `LIFECYCLE` (Intake→…→Verify); `deltafuse.bench.loader.STAGES`
  теперь ссылка на него, дублей имени стадий в коде больше нет.
- **`check_exact_lifecycle(stage_rows)`** (scripts/qualify.py): точное
  равенство имён и порядка, отсутствие duplicate/extra/missing, каждый
  статус `completed`; диагностическое сообщение содержит ожидаемый и
  фактический наборы (missing/unknown/duplicated/got, order).
- **apply_thresholds T2** использует `check_exact_lifecycle` вместо
  `completed < 7`.
- **process** в `_build_run_report` считается только из канонического
  множества стадий и зажат в 0..100.
- **evaluate_medians**: NaN больше не проходит сравнения с лимитом
  (`value != value` → unmeasured; booleans отклоняются); явно применены
  пороги к median correctness (T1: 0..100, иначе unmeasured/invalid, <100 →
  fail) и median process (T2: аналогично).

## Проверки

- Red→Green: 8 completed; 7 произвольных; duplicate Verify; missing Analyze;
  переставленные стадии; skipped/aborted/неизвестный статус — все дают
  диагностический fail; mutation каждой позиции канонического lifecycle
  меняет вердикт.
- Median correctness/process: missing, NaN, boolean, <100, >100 — fail;
  NaN в median T4 тоже больше не проходит.
- Регрессия: 38 тестов qualification-набора зелёные.
