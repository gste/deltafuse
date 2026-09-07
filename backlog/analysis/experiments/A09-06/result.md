# Результат эксперимента A09-06

- **ID карточки:** A09-06
- **Ревизия старта:** `8dbfb21`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `CODE-001`, `CODE-005`, `TEST-001`
- **Вердикт:** **fail** — 0/3 не дошли до Target/Implement. Prompts по holdout **не** подкручивали.

Holdout S08a (рефакторинг без смены поведения). Frozen `:1240`. Extras S02/S03/S04 в prompt не входили, в том числе S03 «не редактируй spec». Oracle/hidden_suite не входили. Seed: живой `security.ratelimit`.

Живой `docs/spec/security/ratelimit.md` **не изменён** ни в одном повторе. Фиктивного behavioural Red нет (Target не запускали). Кода `backends.py` нет.

Routing `primary_capability: ratelimit` (не `security.ratelimit`); поля `type: refactoring` нет.

## S08a r1-frozen (`work/S08a-r1/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.5 с / 42.0 с | CR-* |
| Analyze routing | pass | 1 | 10.8 с / 29.5 с | primary `ratelimit` |
| Analyze slices | pass | 1 | 12.3 с / 32.2 с | SLICE-01 |
| Analyze coverage | pass | 1 | 14.1 с / 30.3 с | схема ok |
| Specify | fsm-pass | 3 | 16.5 с / 26.4 с | spec unchanged; delta none |
| Decompose | fail | 3 | 33.2 с / 58.6 с | coverage `task:` extra; 5 task files |

`spec-delta.md`: `requirement_delta: none`, spec не трогать. `change.yaml` `intent: refactor`.

Логи: [runs/S08a/r1-frozen/](runs/S08a/r1-frozen/).

## S08a r2-frozen (`work/S08a-r2/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.6 с / 38.4 с | CR-* |
| Analyze routing | pass | 1 | 10.9 с / 27.7 с | primary `ratelimit` |
| Analyze slices | pass | 1 | 11.7 с / 28.1 с | SLICE-01 |
| Analyze coverage | pass | 1 | 14.0 с / 28.5 с | схема ok |
| Specify | fail | 3 | 0.2 с / 40.3 с | нет spec-delta; slices-строка |

Spec на диске не менялся.

Логи: [runs/S08a/r2-frozen/](runs/S08a/r2-frozen/).

## S08a r3-frozen (`work/S08a-r3/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.6 с / 41.1 с | CR-* |
| Analyze routing | pass | 1 | 10.7 с / 27.9 с | primary `ratelimit` |
| Analyze slices | pass | 1 | 12.1 с / 35.2 с | SLICE-01 |
| Analyze coverage | pass | 1 | 14.3 с / 44.1 с | схема ok |
| Specify | fail | 3 | 16.5 с / 47.3 с | JSON parse ×2; ложный blocked-on-decision |

Spec на диске не менялся.

Логи: [runs/S08a/r3-frozen/](runs/S08a/r3-frozen/).

## Независимо

- Hidden suite: **not-run** (нет рефакторинга в `src/`).
- Spec unchanged: **pass** на всех трёх.
- Fictitious Red: **not-run**.
- Промпты не меняли.

## Handoff

- **Готово A09-06:** `done` / `fail`. Дальше [A09-07](../../packets/A09-07.md) (S08b docs-only) с теми же замороженными prompts.
- Не подкручивать Specify под «delta none» / `kind: refactoring`. Skills не патчить.
