# Результат эксперимента A09-02

- **ID карточки:** A09-02
- **Ревизия старта:** `9b8371a`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-004`, `CODE-001`, `TEST-001`, `TEST-004`, `PROC-004`
- **Вердикт:** **fail** — 0/3 повторов не дошли до Target/Implement/hidden suite. Prompts по holdout **не** подкручивали.

Holdout S01 (пустой продукт, новая capability). Frozen `:1240`, thinking off. Калибровочные extras S02/S03/S04 в prompt S01 не входили (только WRAPPER + skill + routing-first Analyze + CR-NNN). Oracle/hidden_suite в prompt не входили.

## S01 r1-frozen (`work/S01-r1/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 12.0 с / 37.3 с | CR-* |
| Analyze routing | pass | 1 | 10.8 с / 23.2 с | схема ok |
| Analyze slices | pass | 1 | 9.8 с / 24.1 с | схема ok |
| Analyze coverage | pass | 1 | 11.7 с / 20.7 с | схема ok |
| Specify | fail | 3 | 20.0 с / 47.1 с | нет живого `ratelimit.md`; slices как строка |

Модель писала `docs/spec/limiter/requirements.yaml` и ломала catalog. Specify остановлен. Target не запускали.

Логи: [runs/S01/r1-frozen/](runs/S01/r1-frozen/).

## S01 r2-frozen (`work/S01-r2/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 12.8 с / 41.0 с | CR-* |
| Analyze routing | pass | 1 | 12.0 с / 26.2 с | схема ok |
| Analyze slices | pass | 1 | 11.0 с / 26.6 с | схема ok |
| Analyze coverage | pass | 1 | 12.7 с / 23.3 с | схема ok |
| Specify | fsm-pass, vacuous | 3 | 16.2 с / 48.0 с | нет `ratelimit.md`; [F-010](../../../findings/F-010.md) |
| Decompose | fail | 3 | 25.5 с / 54.4 с | `change.yaml` slices/tasks не той формы |

`check_gate(specified)` зелёный из‑за факта `spec-delta.md`. Живая spec и catalog oracle — нет. Decompose: status `normalized`, tasks как объекты, id `TASK-001-token-bucket-core`.

Логи: [runs/S01/r2-frozen/](runs/S01/r2-frozen/).

## S01 r3-frozen (`work/S01-r3/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 12.5 с / 40.4 с | CR-* |
| Analyze routing | pass | 1 | 12.3 с / 26.5 с | схема ok |
| Analyze slices | pass | 1 | 11.4 с / 31.4 с | схема ok |
| Analyze coverage | pass | 1 | 13.6 с / 27.9 с | схема ok |
| Specify | fail | 3 | 21.9 с / 81.1 с | deltas/slices schema; spec-delta frontmatter |

Логи: [runs/S01/r3-frozen/](runs/S01/r3-frozen/).

## Независимо

- Hidden suite: **not-run** (нет `src/ratelimit/limiter.py`).
- `docs/spec/security/ratelimit.md`: ни в одном повторе.
- Verify: не запускали.
- Промпты калибровки не меняли по этим логам.

## Handoff

- **Готово A09-02:** `done` / `fail`. F-010 → A12. Дальше [A09-03](../../packets/A09-03.md) (S05 holdout) с теми же замороженными prompts.
- Не подкручивать Specify extras под S01. Skills/`integrity.py` не патчить.
- Калибровочные S02-подсказки (cooldown spec, `change.yaml` decomposed) были несущими; без них ornith не закрывает bootstrap.
