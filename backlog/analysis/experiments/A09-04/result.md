# Результат эксперимента A09-04

- **ID карточки:** A09-04
- **Ревизия старта:** `b1ee4d3`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-003`, `PROC-004`, `TEST-001`
- **Вердикт:** **fail** — 0/3 не дошли до Target/Implement/hidden suite. Prompts по holdout **не** подкручивали.

Holdout S06 (длинный raw input / bounded intake). Frozen `:1240`, thinking off. Калибровочные extras S02/S03/S04 в prompt не входили. Oracle/hidden_suite/fault_suite в prompt не входили. Seed: живой `security.ratelimit`.

Фикстура `cases/S06/input.md` — 31 строка с многоточием, не 200 строк лога из манифеста. Лестницу размера не разворачивали.

## S06 r1-frozen (`work/S06-r1/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 14.4 с / 52.5 с | claims есть; oracle CR-id remap |
| Analyze routing | pass | 1 | 11.2 с / 31.3 с | схема ok |
| Analyze slices | pass | 2 | 15.3 с / 35.5 с | только SLICE-01 |
| Analyze coverage | pass | 1 | 14.5 с / 30.6 с | схема ok |
| Specify | blocked-on-decision | 1 | 19.1 с / 95.3 с | ложный DEC; oracle `expected_decision_needed: false` |

DEC `DEC-001-monitoring-runtime` (id вне схемы). `check_gate(specified)` красный; харнесс остановился из‑за JSON `blocked-on-decision` + файла DEC. Нет `audit_log.md`.

Логи: [runs/S06/r1-frozen/](runs/S06/r1-frozen/).

## S06 r2-frozen (`work/S06-r2/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 14.6 с / 54.6 с | claims есть; CR-002 = шум |
| Analyze routing | pass | 1 | 11.3 с / 35.6 с | схема ok |
| Analyze slices | pass | 1 | 14.0 с / 35.0 с | только SLICE-01 |
| Analyze coverage | pass | 1 | 16.1 с / 45.6 с | схема ok |
| Specify | blocked-on-decision | 2 | 18.5 с / 91.0 с | ложный DEC окна/порога, уже данных во входе |

Попытка 1 — JSON parse error. DEC `DEC-20260905-001`. Нет живого `audit_log.md`.

Логи: [runs/S06/r2-frozen/](runs/S06/r2-frozen/).

## S06 r3-frozen (`work/S06-r3/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 14.4 с / 55.3 с | claims есть; oracle CR-id remap |
| Analyze routing | pass | 1 | 11.5 с / 28.7 с | схема ok |
| Analyze slices | pass | 1 | 13.2 с / 32.9 с | только SLICE-01 |
| Analyze coverage | pass | 1 | 14.2 с / 38.4 с | схема ok |
| Specify | fsm-pass, vacuous | 2 | 18.6 с / 33.0 с | нет `audit_log.md`; [F-010](../../../findings/F-010.md) |
| Decompose | fail | 3 | 30.8 с / 76.4 с | coverage.tasks как пути |

Audit вшит в `ratelimit.md` как REQ-RL-05/06. Алерт в живой spec отсутствует (отложен на ненаписанный срез). Catalog без `monitoring.audit_log`.

Логи: [runs/S06/r3-frozen/](runs/S06/r3-frozen/).

## Независимо

- Hidden suite: **not-run** (нет `src/ratelimit/audit.py`).
- `docs/spec/monitoring/audit_log.md`: ни в одном повторе.
- Phantom claims с `internal_gc` в заголовке: нет.
- Verify: не запускали.
- Промпты не меняли.

## Handoff

- **Готово A09-04:** `done` / `fail`. Дальше [A09-05](../../packets/A09-05.md) (S07 holdout) с теми же замороженными prompts.
- Не подкручивать Specify против ложных DEC. Skills не патчить.
- Frozen харнесс считает `blocked-on-decision` + любой DEC-файл терминальным даже при `gate_exit 1` и неверном DEC id. Для A12, не для holdout-тюнинга.
