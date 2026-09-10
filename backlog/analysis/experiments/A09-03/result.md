# Результат эксперимента A09-03

- **ID карточки:** A09-03
- **Ревизия старта:** `f3f2b6d`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-005`, `CODE-002`, `CODE-003`, `TEST-001`, `PROC-004`
- **Вердикт:** **fail** — 0/3 повторов не дошли до Target/Implement/hidden suite. Prompts по holdout **не** подкручивали.

Holdout S05 (существующий `security.ratelimit`, две новые capability + интеграция). Frozen `:1240`, thinking off. Калибровочные extras S02/S03/S04 в prompt не входили (только WRAPPER + skill + routing-first Analyze + CR-NNN). Oracle/hidden_suite/fault_suite в prompt не входили. Seed: живые `docs/spec/security/ratelimit.md` + `src/ratelimit`.

Frozen Analyze extra по-прежнему пишет только `SLICE-01.md` и мапит CR-* на него; оракул S05 ждёт ≥2 среза. Это ограничение заморозки, не тюнинг.

## S05 r1-frozen (`work/S05-r1/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.8 с / 56.3 с | CR-* |
| Analyze routing | pass | 1 | 13.0 с / 42.0 с | схема ok |
| Analyze slices | pass | 1 | 14.2 с / 41.5 с | только SLICE-01 |
| Analyze coverage | pass | 1 | 16.5 с / 35.8 с | схема ok |
| Specify | fail | 3 | 0.2 с / 71.3 с | нет `rate_policy.md`; slices как строка; spec-delta без `---` |

`docs/spec/monitoring/usage_stats.md` появился; catalog без `security.rate_policy`. Specify остановлен. Target не запускали.

Логи: [runs/S05/r1-frozen/](runs/S05/r1-frozen/).

## S05 r2-frozen (`work/S05-r2/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 11.4 с / 48.9 с | CR-* |
| Analyze routing | pass | 1 | 11.3 с / 29.5 с | схема ok |
| Analyze slices | pass | 1 | 12.6 с / 38.9 с | только SLICE-01 |
| Analyze coverage | pass | 1 | 15.0 с / 27.1 с | схема ok |
| Specify | fsm-pass, vacuous | 3 | 18.6 с / 35.9 с | нет `usage_stats.md` / `rate_policy.md`; [F-010](../../../findings/F-010.md) |
| Decompose | fail | 3 | 33.5 с / 132.3 с | coverage.tasks как пути; slices очищены |

Обе новые capability записаны как REQ-RL-05..07 в существующий `ratelimit.md` и в catalog ссылаются на тот же файл. `check_gate(specified)` зелёный из‑за `spec-delta.md`.

Логи: [runs/S05/r2-frozen/](runs/S05/r2-frozen/).

## S05 r3-frozen (`work/S05-r3/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 10.8 с / 53.8 с | CR-* |
| Analyze routing | pass | 1 | 12.6 с / 43.5 с | схема ok |
| Analyze slices | pass | 1 | 14.4 с / 35.0 с | только SLICE-01 |
| Analyze coverage | pass | 1 | 16.6 с / 36.4 с | схема ok |
| Specify | fail | 3 | 22.6 с / 120.0 с | JSON `blocked-on-decision` без DEC; нет `rate_policy.md` |

Живой `usage_stats.md` есть; `rate_policy` в catalog указывает на `ratelimit.md`. На третьей попытке появился SLICE-02 со статусом `blocked-on-decision` и пустым `decisions`.

Логи: [runs/S05/r3-frozen/](runs/S05/r3-frozen/).

## Независимо

- Hidden suite: **not-run** (нет `src/ratelimit/stats.py` / `policy.py` / интеграционных тестов).
- Oracle spec paths: ни один повтор не создал пару `docs/spec/monitoring/usage_stats.md` + `docs/spec/security/rate_policy.md`.
- Verify: не запускали.
- Промпты калибровки не меняли по этим логам.

## Handoff

- **Готово A09-03:** `done` / `fail`. F-010 подтверждается на S05. Дальше [A09-04](../../packets/A09-04.md) (S06 holdout) с теми же замороженными prompts.
- Не подкручивать Specify/Analyze extras под два среза S05. Skills/`integrity.py` не патчить.
- Frozen Analyze «только SLICE-01» не обобщается на мульти-capability holdout; это наблюдение для A12, не основание менять prompts в A09.
