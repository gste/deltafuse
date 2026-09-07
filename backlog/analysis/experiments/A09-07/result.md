# Результат эксперимента A09-07

- **ID карточки:** A09-07
- **Ревизия старта:** `5e0ca35`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-006`, `PROC-003`
- **Вердикт:** **fail** — 0/3 не сошлись. Prompts по holdout **не** подкручивали.

Holdout S08b (docs-only: примеры, RFC 2697 / Leaky Bucket, опечатка «скокрость»→«скорость», CHANGELOG; код/тесты не трогать). Frozen `:1240`. Extras S02/S03/S04 в prompt не входили. Oracle/hidden_suite не входили. Seed: живой `security.ratelimit` плюс опечатка в `refill_rate`.

Specify на всех трёх повторах записал примеры + RFC 2697 + Leaky Bucket + «скорость». Routing `primary_capability: ratelimit`; поля `type: docs` нет (схема routing его не содержит).

## S08b r1-frozen (`work/S08b-r1/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.4 с / 44.9 с | CR-* |
| Analyze routing | pass | 1 | 11.0 с / 31.6 с | primary `ratelimit`; нет `type` |
| Analyze slices | pass | 1 | 12.2 с / 37.5 с | SLICE-01 |
| Analyze coverage | pass | 1 | 14.4 с / 30.5 с | схема ok |
| Specify | pass | 3 | 18.8 с / 49.2 с | примеры/RFC/typo/CHANGELOG; REQ сохранены; `src/` нет |
| Decompose | fail | 3 | 38.6 с / 77.4 с | tasks как пути; slices string |

`intent: documentation`. Код `limiter.py` hash `6a3bdd312dd7` как seed.

Логи: [runs/S08b/r1-frozen/](runs/S08b/r1-frozen/).

## S08b r2-frozen (`work/S08b-r2/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.8 с / 46.5 с | CR-* |
| Analyze routing | pass | 1 | 11.0 с / 29.6 с | primary `ratelimit`; нет `type` |
| Analyze slices | pass | 1 | 13.0 с / 32.7 с | SLICE-01 |
| Analyze coverage | pass | 1 | 14.4 с / 28.9 с | схема ok |
| Specify | pass | 3 | 18.9 с / 94.4 с | docs extras; REQ-RL-03 переписан |
| Decompose | pass | 1 | 22.2 с / 107.7 с | TASK-001 docs-only paths |
| Target TASK-001 | already-green | 1 | 28.9 с / 58.3 с | pytest seed green; red/ README |
| Implement TASK-001 | fail | 3 | 30.8 с / 44.3 с | harness требует `limiter.py`; сломан `is_blocked` |

Попытка 1 Implement писала spec+CHANGELOG — `parse_error: implement must write src/ratelimit/limiter.py`. Попытки 2–3 переписали `limiter.py` (`546592bf1f4c`); `is_blocked` больше не всегда False.

Логи: [runs/S08b/r2-frozen/](runs/S08b/r2-frozen/).

## S08b r3-frozen (`work/S08b-r3/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.5 с / 39.3 с | CR-* |
| Analyze routing | pass | 1 | 10.7 с / 28.0 с | primary `ratelimit`; нет `type` |
| Analyze slices | pass | 1 | 11.8 с / 30.3 с | SLICE-01 |
| Analyze coverage | pass | 1 | 13.9 с / 23.9 с | схема ok |
| Specify | pass | 2 | 16.4 с / 55.0 с | примеры/RFC/typo; CHANGELOG пустой Unreleased |
| Decompose | fail | 3 | 25.8 с / 61.7 с | tasks как пути; slices без `file` |

Код не менялся. CHANGELOG без записи о документации.

Логи: [runs/S08b/r3-frozen/](runs/S08b/r3-frozen/).

## Независимо

- Hidden suite: **fail** на r2 (код изменён); r1/r3 код не тронут, но `route_type: docs` в routing.yaml нет.
- Docs extras (примеры, RFC 2697, Leaky, typo): **pass** на Specify во всех трёх.
- Фиктивный Red: r2 Target `already-green` + evidence/red (ожидаемо для docs-only pytest).
- Frozen harness Implement всегда требует `src/ratelimit/limiter.py` — docs-only не может закрыть Implement без правки кода. Не тюнить.
- Промпты не меняли.

## Handoff

- **Готово A09-07:** `done` / `fail`. Дальше [A09-08](../../packets/A09-08.md) (S08c operational) с теми же замороженными prompts.
- Не подкручивать Decompose `TASK-NNN` / Implement «не пиши limiter». Skills не патчить.
- Target/Implement как обязательный Red/Green на docs-only — [Q-005](../../parking/design-questions.md).
