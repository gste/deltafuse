# QF-008 — schema, медианы и сохранение отказов

- **Приоритет:** P1
- **Зависимости:** QF-006 (поля `evidence_authentic`, breakdown-метрики)
- **Commit:** `qualify: validate reports and preserve failures`
- **Исходный дефект:** [qualification-fix-plan.md, QF-008](../../qualification-fix-plan.md)
- **Код на момент написания:** commit `bb02820` + QF-001…QF-007

Исполнитель: читай [README.md](../README.md); конвенция «Схемы артефактов
qualification» вводится этим пакетом.

## 1. Дефекты

Все — в `scripts/qualify.py` (`run_case`, `medians`, `main`; bb02820):

1. **Disk report не соответствует формату
   [thresholds.md](../../thresholds.md) «Per-run disk report»**:
   - `stages` — dict сырых stage-результатов scorecard (со `checks`-списками,
     metrics и пр.), а не список `{stage, status, checks:{passed,failed},
     gate_retries}`;
   - нет `totals` (correctness {passed, failed}, gate_retries,
     context_peak_tokens, max_unique_files, hallucinated_paths,
     envelope_violations, evidence_authentic);
   - нет полного набора полей, по которым visible verdict.
2. **`medians()` не считает process** (только correctness, контексты,
   retries, files) — медиана process из thresholds-таблицы release report
   не вычисляется.
3. **`runs_ok` протекает между cases**: переменная инициализируется один
   раз до цикла по всем cases; fail в M01-run2 делает verdict каждого
   следующего case `fail` независимо от его собственных runs, и наоборот —
   verdict case не отражает именно его runs.
4. **Ошибка HTTP/score/I/O завершает run без failure report**: исключение
   из `run_case` ловится в `main`, manifest помечается `incomplete`, но
   per-run `report.yaml` для начатого run не создаётся — run исчезает из
   evidence; класс ошибки не фиксируется.

## 2. Нормативное поведение

### 2.1 Схемы артефактов

JSON Schema draft 2020-12, каталог `scripts/schemas/`:

- `run-report.schema.json` — per-run report по формату thresholds.md:
  `schema_version, run_id, case, verdict, framework_commit, model,
  threshold_failures[], stages[] (stage,status,checks{passed,failed},
  gate_retries), calls[] (input_tokens, framework_input_tokens,
  framework_input_chars, framework_input_tokens_method, unique_files,
  hallucinated_paths, envelope_violations), totals{correctness{passed,
  failed}, gate_retries, context_peak_tokens, framework_input_tokens_max,
  max_unique_files, hallucinated_paths, envelope_violations,
  evidence_authentic}, t7_breakdown?, hallucinated_breakdown?,
  tool_events[], error?{class, detail}`;
- `run-manifest.schema.json` — campaign manifest: существующие поля +
  `case_verdicts{}.medians{correctness, process, context_peak_tokens,
  framework_input_tokens_max, gate_retries, max_unique_files}` +
  `runs[].error{class, detail}` + `model`-структура QF-007.

Валидация `jsonschema` (уже в requirements-dev) — **перед каждой атомарной
записью** manifest/report: невалидный документ не пишется никогда; вместо
этого — сохранение классифицированной ошибки (см. 2.4) и ненулевой exit.

### 2.2 Per-run report по thresholds.md

`run_case` строит report строго по схеме: stages конвертируются из
scorecard-формата в компактный список (status: `completed|failed|skipped`;
`checks.passed/failed` из `checks_passed/checks_total`); `totals` —
агрегаты run; `evidence_authentic` — из QF-006; исходная scorecard
сохраняется рядом как `scorecard.yaml` (диагностика, схемой не валидируется).

### 2.3 Медианы и изоляция case

- `medians(runs)` считает `correctness` И `process` (+ существующие);
  отсутствующее значение исключает метрику из медианы, но presence-check
  ниже не даёт этому пройти бесследно.
- Состояние verdict вычисляется per-case: `case_ok = все runs case пройдены
  и медианы пройдены`; глобальный verdict = `pass` только если все cases
  пройдены и набор полон. Никаких сквозных булевых.
- Median-оценка перестаёт использовать carrier-заглушки: T1/T2 для медиан
  вычисляются из фактических данных runs (если хоть один run имеет
  correctness_failed>0 / неполные стадии — case уже failed per-run;
  медианы дополнительно проверяют границы T3–T7 и T8-полноту набора).

### 2.4 Классификация ошибок и failure reports

- Классы: `host_error` (HTTP/timeout к LM Studio), `score_error`
  (score_product/BenchError), `io_error` (запись на диск), `schema_error`
  (валидация), `internal_error` (прочее; с traceback-хвостом).
- Каждый **начатый** run обязан иметь `report.yaml`: при исключении run'
  создаётся report с `verdict: fail`, `error{class, detail}`,
  `threshold_failures: ["run_error:<class>"]`, валидируется схемой и
  атомарно пишется до выхода из main.
- main: после классификации ошибки кампания **продолжает** следующие runs,
  если ошибка изолирована в run'е (host_error прерывает кампанию целиком —
  host один на кампанию); любой error-run → глобальный non-zero exit.
  Exit codes зафиксировать: 0 pass; 1 fail; 2 pending (host недоступен
  до начала); 3 provenance/конфигурация; 4 ошибка записи manifest.

## 3. План работ

### Шаг 1 — Red-тесты (`tests/unit/test_qualify.py`; схемы — новый файл
`tests/unit/test_qualify_schemas.py`)

- `test_report_matches_schema` — синтетический полный run: report
  валиден по `run-report.schema.json` (validator.iter_errors пуст).
- `test_report_has_thresholds_md_shape` — в report есть `stages`-список с
  `{stage,status,checks{passed,failed},gate_retries}` и `totals` с
  обязательными ключами, включая `evidence_authentic`.
- `test_schema_rejects_missing_totals` — удаление `totals`/поля →
  невалидно.
- `test_medians_include_process` — медианы трёх runs с process
  {70,80,90} → 80; без process-значений → медиана process None и
  median-оценка это трактует как fail (пустая медиана не pass).
- `test_case_verdicts_isolated` — кампания 2 cases × 1 run: run M01 fail,
  run M02 pass → `case_verdicts[M02].verdict == "pass"`, M01 — fail,
  глобальный fail (сегодня M02 ошибочно fail).
- `test_failed_run_saves_failure_report` — monkeypatch `run_case` →
  бросает `score_error` на 2-м run: после main все начатые runs имеют
  report.yaml; run 2 — `verdict: fail`, `error.class: score_error`;
  exit ≠ 0.
- `test_host_error_aborts_with_reports` — host_error на run 1: кампания
  останавливается, manifest `verdict: incomplete`, report run 1 записан
  с ошибкой, exit ≠ 0.
- `test_manifest_valid_against_schema` — manifest синтетической кампании
  валиден по `run-manifest.schema.json`.
- Обновить `test_synthetic_campaign_with_failure_is_nonzero_and_saves_all`
  под новую структуру report (проверки totals/stages-формата).

### Шаг 2 — Реализация

1. Схемы в `scripts/schemas/` (+ при необходимости мини-загрузчик
   `qualify_schemas.py`).
2. `build_run_report(...)` — конверсия scorecard → формат 2.2;
   `build_manifest(...)`; обе — с валидацией до записи.
3. `medians()` — process + поведение 2.3; удалить carrier-заглушки в
   `main`.
4. `run_case`/`main`: try/except-обёртка классификации (2.4), failure-
   report writer, per-case verdict state; exit codes 2.4.
5. `scorecard.yaml` рядом с report.yaml (диагностика).

### Шаг 3 — Регрессия

- Полный suite + оба smoke; `git status --porcelain` чист после прогонов
  (RUNS_DIR в тестах — tmp_path; реальная кампания не запускается).

## 4. Границы и запреты

- Формат thresholds.md — источник истины: если схема и thresholds.md
  расходятся, чинится схема (не thresholds.md).
- Не выбрасывать диагностику: сырой scorecard сохраняется рядом.
- Ошибка записи manifest (OSError) не маскирует verdict: обе проблемы
  фиксируются (существующий write_error-механизм сохранить).

## 5. Acceptance

- [ ] Schema validation проходит на всех сохранённых файлах (тесты).
- [ ] Report соответствует формату thresholds.md (stages-список, totals,
      evidence_authentic).
- [ ] Медианы correctness и process считаются; незавершённый набор /
      failed run / failed median не даёт pass (тесты).
- [ ] Кампания 3×3 с failed run + отсутствующим measurement + ошибкой
      записи/host: все начатые runs в manifest/report, exit ненулевой.
- [ ] Verdict'ы cases изолированы.
- [ ] Полный suite + smoke зелёные.

## 6. Evidence для RESULT.md

1. Red-вывод новых тестов.
2. Green suite + smoke.
3. Дерево синтетической кампании из тестов (листинг report/manifest/
   scorecard файлов) и `python -c` пример валидации schema.

## 7. Commit

Один commit: `qualify: validate reports and preserve failures`.
Состав: `scripts/qualify.py`, `scripts/schemas/*.json`,
`tests/unit/test_qualify.py`, `tests/unit/test_qualify_schemas.py`,
`RESULT.md`.
