# Результат эксперимента A09-10

- **ID карточки:** A09-10
- **Ревизия старта:** `5b96f51`
- **Статус исполнения:** **done**
- **Критерии:** `PROC-002`, `PROC-003`, `PROC-005`
- **Вердикт:** **fail** — 0/3 не дошли до Target Red; interrupt/resume/re-slice не измерялись. Prompts по holdout **не** подкручивали.

Holdout S10 (история `consume` / `get_history`, затем evaluator interrupt после Red и follow-up персистенции). Frozen `:1240`. Extras S02/S03/S04 в prompt не входили. Oracle/hidden_suite/fault_suite не входили. Seed: живой `security.ratelimit`. Follow-up из `cases/S10/manifest.yaml` инжектируется только после Implement — до Target не дошли, текст не подставляли.

`limiter.py` без `get_history` на всех трёх. Живой spec на всех трёх получил REQ-RL-05+. Один Change на повтор. Interrupt checkpoint не создавался.

## S10 r1-frozen (`work/S10-r1/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 7.8 с / 38.1 с | `CHG-001-ratelimit-consume-history`; CR-001..006 |
| Analyze routing | pass | 1 | 11.8 с / 23.9 с | `security.ratelimit` |
| Analyze slices | pass | 1 | 12.3 с / 28.1 с | SLICE-01 |
| Analyze coverage | pass | 1 | 12.6 с / 26.7 с | схема ok |
| Specify | fail | 3 | 17.9 с / 60.7 с | a1 нет spec-delta; a2 нет `---`; a3 `added: REQ-RL-05..08` как файлы |

Логи: [runs/S10/r1-frozen/](runs/S10/r1-frozen/).

## S10 r2-frozen (`work/S10-r2/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 11.5 с / 40.4 с | тот же Change id; CR-001..008 |
| Analyze routing | pass | 1 | 11.8 с / 29.2 с | `primary_capability: ratelimit` |
| Analyze slices | pass | 1 | 12.4 с / 39.0 с | SLICE-01 |
| Analyze coverage | pass | 1 | 14.9 с / 32.4 с | схема ok |
| Specify | fail | 3 | 19.2 с / 85.0 с | slices без `file`; spec-delta без frontmatter |

Логи: [runs/S10/r2-frozen/](runs/S10/r2-frozen/).

## S10 r3-frozen (`work/S10-r3/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 11.2 с / 47.4 с | `CHG-001-ratelimit-history` |
| Analyze routing | pass | 1 | 11.2 с / 27.7 с | `primary_capability: ratelimit` |
| Analyze slices | pass | 1 | 11.8 с / 36.3 с | SLICE-01 |
| Analyze coverage | pass | 1 | 16.0 с / 31.6 с | схема ok |
| Specify | fail | 3 | 18.6 с / 89.3 с | как r2; a3 нет JSON |

Логи: [runs/S10/r3-frozen/](runs/S10/r3-frozen/).

## Независимо

- Interrupt/resume/re-slice: **not-run** (остановка на Specify, Red нет).
- Hidden suite: **not-run** (нет checkpoint, нет cancelled/superseded, нет `data/consume-history.jsonl`).
- [F-005](../../../findings/F-005.md) на ornith **не** подтверждали и **не** ослабляли оракул.
- Модельный CR-003 = `get_history`, не oracle persistence CR-003.
- Промпты не меняли.

## Handoff

- **Готово A09-10:** `done` / `fail`. Дальше [A09-11](../../packets/A09-11.md) (S11 два Change / удаление) с теми же замороженными prompts.
- Не подкручивать Specify под spec-delta frontmatter. Skills не патчить.
