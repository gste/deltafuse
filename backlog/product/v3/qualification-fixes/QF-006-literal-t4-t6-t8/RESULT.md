# QF-006 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `cbe4a0b` (QF-005)
- **Инструменты:** Python .venv 3.12.14 (uv), pytest, git 2.45.1, Windows 10.0.26200

## Реализация (`scripts/qualify.py`)

- **T4 / provenance**: `drive_worker` ведёт `message_meta` (origin =
  system|framework|product, source = system-prompt|seed|core-command|
  runner-protocol|file-read|shell-noncore). Тела прочитанных файлов и вывод
  не- Core shell — `product` и не входят в framework-часть.
  `framework_input_chars` — точное целое по provenance-тегам;
  `framework_input_tokens` — host-токенизатор `_host_tokenize`
  (`POST /api/v0/tokenize`, кэш по sha256), при недоступности — оценка
  `chars // 4`; метод (`host-tokenize|chars-div-4|mixed`) записан в каждом
  call-entry и в метриках run. `apply_thresholds` требует наличия
  `framework_input_chars` (иначе `T4 framework_input_chars=unmeasured`).
- **T6**: `classify_violations(events)` — матрица 2.2 по типизированному
  журналу: отсутствующий read / неразрешимый write / unknown tool /
  неизвестный subcommand / pytest exit 4 → hallucinated (T6); Core-owned,
  вне-envelope, отказы политики исполнения (operators/env/options/@/absolute/
  traversal) → T7 (`write_denied`, `execution_policy` в `t7_breakdown`).
  Счётчики `hallucinated_paths` в местах событий приведены в соответствие
  матрице (write-escape и неизвестные subcommand теперь T6); run-метрики
  (`hallucinated_paths`, `hallucinated_breakdown`) производны от журнала.
- **T8**: `REQUIRED_T8_CHECKS = {journal_forgery, synthetic_evidence,
  oracle_leak}`; `evidence_authentic(report)` — true только при полном
  наборе пройденных проверок; `apply_thresholds` даёт
  `T8 evidence_missing=...` при отсутствии любой обязательной (пустой
  `defense_checks` валит T8). `run_case` пишет `evidence_authentic`,
  `hallucinated_breakdown`, `framework_input_tokens_method`,
  `framework_input_chars_max` в per-run report.

## Red-фаза (до реализации)

```
FAILED test_t4_framework_excludes_product_content
FAILED test_t4_framework_tokens_method_recorded
FAILED test_t4_unmeasured_framework_chars_fails
FAILED test_t6_matrix_rows - AttributeError: classify_violations
FAILED test_t6_shell_rejected_unknown_tool_is_hallucination
FAILED test_t8_empty_defense_checks_fails - AttributeError: REQUIRED_T8_CHECKS
FAILED test_t8_missing_required_check_fails - AttributeError
FAILED test_t8_evidence_authentic_flag - AttributeError
```

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests
423 passed, 1 skipped, 54 warnings in 238.94s   (0 failed)
```

Smoke: ps1 rc=0, sh rc=0.

## Изменения контракта (ожидаемые по инструкции)

- `defense_checks={}` больше не даёт T8 pass: фикстуры
  `test_thresholds_t1_to_t8` / `_passing_report_and_metrics` /
  median-carrier в `main()` обновлены на полный набор обязательных проверок.
- `test_sandbox_io_rejects_escapes`: write в неразрешимый путь и отказ
  с absolute-путём переклассифицированы по матрице (T6/T7 соответственно).
- Медианы и median-carrier учитывают `framework_input_chars_max`.

## Acceptance

- [x] T4: usage + provenance-символы + метод токенизации измеряемы в report;
      product content исключён из framework-части.
- [x] T6: `hallucinated_breakdown` из журнала по матрице (тест каждой строки).
- [x] T8: обязательный набор; пустой `defense_checks` валит verdict;
      `evidence_authentic` false при пропуске/провале.
- [x] `0` не подставляется вместо unknown (мутации unmeasured зелёные).
- [x] Полный suite 0 failed; оба smoke rc=0.
