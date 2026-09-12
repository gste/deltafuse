# QF-008 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `048063f` (QF-007)
- **Инструменты:** Python .venv 3.12.14, pytest, jsonschema 4.26.0, Windows 10.0.26200

## Реализация

- **Схемы** (`scripts/schemas/`, draft 2020-12): `run-report.schema.json`
  (формат thresholds.md: stages-список `{stage,status,checks,gate_retries}`,
  `totals` с `correctness{passed,failed}`/…/`evidence_authentic`,
  опциональный `error{class,detail}`); `run-manifest.schema.json`
  (campaign manifest: attested `model` QF-007, `runs[]` с
  `error{class,detail}`, `case_verdicts{}.medians{correctness, process,
  context_peak_tokens, framework_input_tokens_max, gate_retries,
  max_unique_files}`, verdict enum pass|fail|incomplete|pending).
- `validate_document(kind, doc)` + `_atomic_write_yaml_validated`:
  валидация **перед каждой** атомарной записью; невалидный документ не
  пишется никогда (SchemaValidationError).
- `run_case`: `_build_run_report` конвертирует scorecard в формат
  thresholds.md; сырой scorecard сохраняется рядом как `scorecard.yaml`;
  report валидируется схемой. score_product ошибки → `ScoreError`.
- **Медианы**: `medians()` добавляет `process` (доля completed-стадий),
  `hallucinated_paths`, `envelope_violations`; `evaluate_medians()` проверяет
  границы T3–T7 и T8-полноту по фактическим runs — carrier-заглушки удалены.
- **Изоляция case**: per-case `case_ok`; сквозные булевы удалены.
- **Ошибки**: классы `HostError/ScoreError/IoError/SchemaValidationError` +
  `classify_exception` (host/score/io/schema/internal); каждый начатый run
  получает валидированный failure report (`verdict: fail`,
  `run_error:<class>`); host_error прерывает кампанию (verdict incomplete,
  exit 3); изолированные ошибки → кампания продолжается, глобальный exit 1.
  Exit codes: 0 pass, 1 fail, 2 pending, 3 provenance/host-abort, 4 write
  error (write_error-механизм сохранён).

Дерево синтетической кампании из тестов:
```
<campaign>/manifest.yaml
<campaign>/<run_id>/report.yaml   (schema-validated)
<campaign>/<run_id>/scorecard.yaml (raw diagnostics)
```
Валидация вручную:
`python -c "import sys; sys.path.insert(0,'scripts'); import qualify, yaml; qualify.validate_document('run-manifest', yaml.safe_load(open('manifest.yaml')))"`

## Red-фаза (на HEAD qualify.py до реализации)

```
FAILED test_report_matches_schema - AttributeError: validate_document
FAILED test_schema_rejects_missing_totals / test_schema_rejects_bad_stage_shape
FAILED test_failure_report_with_error_is_valid
FAILED test_medians_include_process - KeyError: 'process'
FAILED test_case_verdicts_isolated - AssertionError (M02 ошибочно fail)
FAILED test_failed_run_saves_failure_report - AttributeError
FAILED test_host_error_aborts_with_reports - AttributeError
FAILED test_manifest_valid_against_schema - AttributeError
```

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests
439 passed, 1 skipped, 54 warnings in 266.98s   (0 failed)
```

Smoke: ps1 rc=0, sh rc=0.

## Acceptance

- [x] Schema validation проходит на всех сохранённых файлах (report,
      manifest, failure report; тесты + writer).
- [x] Report соответствует формату thresholds.md (stages-список, totals,
      evidence_authentic; scorecard рядом).
- [x] Медианы correctness и process; незавершённый набор / failed run /
      failed median не даёт pass (тесты).
- [x] Failed run / отсутствующий measurement / host-ошибка: все начатые
      runs в manifest и на диске, exit ненулевой.
- [x] Verdict'ы cases изолированы (M01 fail не тянет M02).
- [x] Полный suite 0 failed; оба smoke rc=0.
