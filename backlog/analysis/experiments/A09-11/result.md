# Результат эксперимента A09-11

- **ID карточки:** A09-11
- **Ревизия старта:** `2203b55`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-005`, `SPEC-007`, `TEST-005`, `PROC-002`
- **Вердикт:** **fail** — 0/3 не сошлись; F-006 silent-pass не наблюдали (converged не прошёл). Prompts по holdout **не** подкручивали.

Holdout S11 (CHG-B `get_window_stats` из `input.md`; evaluator CHG-A `burst_allowance`; merge; CHG-C удаление). Frozen `:1240`. Extras S02/S03/S04 в prompt не входили. Oracle/hidden_suite не входили. Seed: живой `security.ratelimit`. Лестница 2→4→8 не запускалась: граница на размере 2.

CHG-B prompt без `burst_allowance`. После r1 merge evaluator копировал seed `limiter.py` CHG-A поверх `get_window_stats`; для r2/r3 merge/C только если Specify CHG-A `pass`.

## S11 r1 CHG-B (`work/S11-r1-chgb/`, tag `frozen-chgb`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.8 с / 43.1 с | `CHG-001-ratelimit-window-stats` |
| Analyze routing | pass | 1 | 11.1 с / 23.9 с | ok |
| Analyze slices | pass | 1 | 11.7 с / 34.4 с | SLICE-01 |
| Analyze coverage | pass | 1 | 14.5 с / 27.5 с | ok |
| Specify | pass | 3 | 17.6 с / 73.4 с | live spec + spec-delta |
| Decompose | pass | 1 | 20.2 с / 145.6 с | TASK-001..004 на диске `pending` |
| Target | already-green | 1 | 32.0 с / 45.7 с | pytest только `test_limiter.py`; Red в `test_window_stats_red.py` |
| Implement | pass | 3 | 31.7 с / 57.5 с | `get_window_stats` в limiter |
| Verify | fail | 3 | 38.9 с / 74.8 с | нет `evidence/verification/run.yaml`; задачи `pending` |

Логи: [runs/S11/r1-frozen-chgb/](runs/S11/r1-frozen-chgb/).

## S11 r1 CHG-A / merge / CHG-C

| Шаг | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| CHG-A Specify | fail | 3 | 19.1 с / 77.6 с | live spec с `burst_allowance`; код без burst |
| Merge verify | fail | 3 | 40.3 с / 77.4 с | spec burst на B; limiter CHG-B затёрт seed CHG-A |
| CHG-C Specify | fail | 3 | 20.2 с / 76.7 с | burst остался в spec |

## S11 r2

CHG-B Specify **fail** (slices без `file`, spec-delta без frontmatter). CHG-A Specify **fail**. Merge/C skipped.

Логи: [runs/S11/r2-frozen-chgb/](runs/S11/r2-frozen-chgb/), [r2-frozen-chga](runs/S11/r2-frozen-chga/).

## S11 r3

CHG-B Specify **fail** (`added: REQ-RL-05..08` как файлы). CHG-A Specify **fail**. Merge/C skipped.

Логи: [runs/S11/r3-frozen-chgb/](runs/S11/r3-frozen-chgb/), [r3-frozen-chga](runs/S11/r3-frozen-chga/).

## Независимо

- Hidden suite: **not-run** (нет `converged` после merge; deletion не закрылась).
- [F-006](../../../findings/F-006.md): stale Green на диске CHG-B r1, но converged не прошёл — silent pass не зафиксирован.
- Target already-green: харнесс гоняет только `tests/test_limiter.py`.
- Лестница 4/8: **not-run**.
- Промпты не меняли.

## Handoff

- **Готово A09-11:** `done` / `fail`. Дальше [A09-12](../../packets/A09-12.md) (S12 недоверенный вход) с теми же замороженными prompts.
- Не подкручивать Specify/Verify. Skills не патчить.
