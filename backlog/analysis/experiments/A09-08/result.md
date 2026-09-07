# Результат эксперимента A09-08

- **ID карточки:** A09-08
- **Ревизия старта:** `5a94495`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-006`, `PROC-003`
- **Вердикт:** **fail** — 0/3 не сошлись. Prompts по holdout **не** подкручивали.

Holdout S08c (ops: hostname `limiter-prod-02`, порт 9090, лог `/opt/logs/ratelimiter/`, health URL, `docs/ops/runbook.md`; код/spec/тесты не трогать). Frozen `:1240`. Extras S02/S03/S04 в prompt не входили. Oracle/hidden_suite не входили. Seed: живой `security.ratelimit` плюс старые `deploy/config.yaml`, `monitoring/health_checks.yaml`, `docs/ops/runbook.md`.

Ops-файлы **не изменены** ни в одном повторе (остались `limiter-prod-01` / 8080). Spec и `limiter.py` совпадают с seed. Routing `primary_capability: ratelimit`; поля `type: operational` нет.

## S08c r1-frozen (`work/S08c-r1/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 11.3 с / 44.5 с | CR-* |
| Analyze routing | pass | 1 | 11.5 с / 26.0 с | primary `ratelimit`; нет `type` |
| Analyze slices | pass | 1 | 12.0 с / 24.2 с | SLICE-01 |
| Analyze coverage | pass | 1 | 13.8 с / 26.6 с | схема ok |
| Specify | fail | 3 | 14.2 с / 44.3 с | coverage extra `spec_delta`; нет frontmatter |

`intent: maintenance`. `spec-delta` текст: `requirement_delta none`, ops не записаны.

Логи: [runs/S08c/r1-frozen/](runs/S08c/r1-frozen/).

## S08c r2-frozen (`work/S08c-r2/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.7 с / 44.2 с | CR-* |
| Analyze routing | pass | 1 | 11.2 с / 22.6 с | primary `ratelimit`; нет `type` |
| Analyze slices | pass | 1 | 11.7 с / 32.4 с | SLICE-01 |
| Analyze coverage | pass | 1 | 13.8 с / 26.3 с | схема ok |
| Specify | fail | 3 | 14.7 с / 42.0 с | JSON parse; ложный blocked-on-decision |

Попытка 2: `blocked-on-decision` без DEC — frozen extra отверг. Ops не тронуты. `spec-delta.md` нет.

Логи: [runs/S08c/r2-frozen/](runs/S08c/r2-frozen/).

## S08c r3-frozen (`work/S08c-r3/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 11.3 с / 46.6 с | CR-* |
| Analyze routing | pass | 1 | 11.1 с / 26.3 с | primary `ratelimit`; нет `type` |
| Analyze slices | pass | 1 | 12.4 с / 32.7 с | SLICE-01 |
| Analyze coverage | pass | 1 | 14.5 с / 27.4 с | схема ok |
| Specify | pass | 3 | 18.0 с / 40.2 с | F-010; delta none; ops не записаны |
| Decompose | fail | 3 | 34.8 с / 146.8 с | tasks как пути; slices без `file` |

4 task-файла про deploy/health/runbook, но coverage хочет ids `TASK-NNN`.

Логи: [runs/S08c/r3-frozen/](runs/S08c/r3-frozen/).

## Независимо

- Hidden suite: **not-run** (нет ops-диффа; `route_type` отсутствует).
- Spec unchanged: **pass** на всех трёх.
- Code/tests unchanged: **pass** на всех трёх.
- Ops (`prod-02`, 9090, `/opt/logs`): **fail** на всех трёх.
- Specify не пишет `deploy/` / `monitoring/` / `docs/ops/`; Implement frozen требует `limiter.py`. [Q-006](../../parking/design-questions.md).
- Промпты не меняли.

## Handoff

- **Готово A09-08:** `done` / `fail`. Дальше [A09-09](../../packets/A09-09.md) (S09 terminal) с теми же замороженными prompts.
- Не подкручивать Specify под ops-файлы. Skills не патчить.
