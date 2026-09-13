# QF-017 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `6267f84` (QF-016)
- **Red evidence:** `tests/unit/test_qualify_semantic.py` — до реализации
  `calls: [{}]`, отсутствующие T4–T7 измерения, лишние поля,
  `pass` с `null`/`error`, `fail` без failures, NaN и противоречивые totals
  проходили (или не проверялись вовсе); semantic-валидации не существовало.

## Реализация

- **`run-report.schema.json`** (strict, `additionalProperties: false` везде):
  `$defs` stage/call/toolEvent/totals/t7Breakdown/breakdown/stage_leash;
  каждый call требует input_tokens, framework_input_chars/tokens +
  метод, unique_files, hallucinated_paths, envelope_violations с точными
  типами. Вердикты разделены `oneOf`:
  - measured pass: все измерения non-null, `threshold_failures: []`,
    `error` запрещён, `evidence_authentic: true`, `correctness.failed = 0`;
  - measured fail: измерения присутствуют, failures непусты, error запрещён;
  - infrastructure failure: `error` обязателен, nullable измерения допустимы.
- **`run-manifest.schema.json`** (strict): runs — компактные ссылки
  {run_id, case, verdict, threshold_failures, error?} (тела отчётов больше
  не дублируются в манифесте); medians — фиксированный набор полей;
  thresholds.absolute — константные пороги T1–T8; executor/attested —
  закрытые блоки provenance; корень `additionalProperties: false`.
- **`scripts/qualify_semantic.py`** (новый):
  - `semantic_validate_report`: totals.correctness пересчитывается из
    stages; max_unique_files = max по calls; NaN отвергается (schema его
    не видит); pass ⇒ без error/failures/незавершённых стадий; error ⇒
    fail + `run_error:*`.
  - `semantic_validate_manifest`: уникальные run IDs; каждый run ссылается
    на существующий schema-valid report.yaml; commit/model совпадают во
    всех artifacts; verdict каждого run равен отчёту; для полной кампании
    пересчитываются case- и campaign-verdict (включая QF-013-cap:
    local-dev не может дать release pass); pending/incomplete — валидные
    частичные состояния.
- **Runner**: `_write_manifest` — schema+semantic валидация перед каждой
  записью (после каждого run и финальная); противоречивый манифест не
  пишется (exit 4). `medians()`/`evaluate_medians()` пересчитывают из
  `totals` при отсутствии верхнеуровневого поля (устранён скрытый дефект:
  реальные reports не содержат gate_retries/context_peak_tokens наверху).

## Проверки

- Mutation-матрица: `calls: [{}]`, каждое отсутствующее измерение, лишнее
  поле, строка/boolean, NaN, pass с null, pass с error, fail без failures,
  duplicate run ID, отсутствующий report, несовпадающий commit/model,
  подменённый verdict, локальный run-count mismatch — все отвергаются.
- Synthetic 3x3 с одним failure сохраняет все результаты и даёт ненулевой
  exit (`test_synthetic_campaign_with_failure_is_nonzero_and_saves_all`).
- Полный qualification-набор: 153 passed.

## Коррекция (QF-024)

- Неверно указанный базовый commit: `6267f84` — этот commit существует в
  репозитории, но НЕ находится в ancestry активной ветки
  `feature/2026-09-11-audit` (alternate/dangling base). Это вариант коммита
  «assets: recover interrupted bundle transactions», финальная версия
  которого вошла в историю как `6b44c66`; RESULT ссылался на непопавшую в
  ветку редакцию.
- Фактический parent commit'а пакета QF-017 (`47c7a40`): `6b44c66c26aad1907aba9da49a5c79002a6c2c61`
  (QF-016). История не переписывалась; настоящая заметка добавлена задним
  числом явно, по правилу 1 QF-024.
