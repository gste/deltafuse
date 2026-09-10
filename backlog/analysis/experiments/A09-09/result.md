# Результат эксперимента A09-09

- **ID карточки:** A09-09
- **Ревизия старта:** `f732a56`
- **Статус исполнения:** **done**
- **Критерии:** `PROC-001`, `PROC-002`, `PROC-006`
- **Вердикт:** **fail** — 1/3 терминальный `duplicate` с provenance. Prompts по holdout **не** подкручивали.

Holdout S09 (дубликат отклонённого CHG-042, цепочка CHG-055→CHG-060, INFRA-789, not-reproduced). Frozen `:1240`. Extras S02/S03/S04 в prompt не входили. Oracle/hidden_suite не входили. Seed: `security.ip_filter` + архив CHG-042/055/060 и INFRA-789.

Spec `ip_filter.md` и `limiter.py` не менялись. Живой Change везде `CHG-061-ipv6-ip-filter`.

## S09 r1-frozen (`work/S09-r1/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 11.3 с / 95.6 с | `status: duplicate`; CHG-042/055/060, INFRA-789 |

JSON `continue`, `change.yaml` `duplicate`. Analyze не запускали.

Логи: [runs/S09/r1-frozen/](runs/S09/r1-frozen/).

## S09 r2-frozen (`work/S09-r2/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | fail | 3 | 7.9 с / 64.8 с | писал coverage/spec-delta; status `normalized` |
| Analyze routing | pass | 1 | 11.9 с / 36.9 с | схема ok |
| Analyze slices | pass | 1 | 14.5 с / 40.1 с | SLICE-01 |
| Analyze coverage | pass | 1 | 16.7 с / 28.8 с | схема ok |
| Specify | fail | 3 | 19.2 с / 52.5 с | status `closed` invalid; extra `specification` |

Provenance в `request.md` есть, терминального статуса нет.

Логи: [runs/S09/r2-frozen/](runs/S09/r2-frozen/).

## S09 r3-frozen (`work/S09-r3/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | blocked-on-decision | 1 | 8.1 с / 63.6 с | DEC yaml, не rejected/duplicate |
| Analyze routing | pass | 1 | 11.5 с / 38.4 с | схема ok |
| Analyze slices | pass | 1 | 13.9 с / 65.3 с | SLICE-01 |
| Analyze coverage | pass | 1 | 15.1 с / 48.1 с | схема ok |
| Specify | pass | 2 | 17.7 с / 75.3 с | F-010; change.yaml всё ещё `blocked-on-decision` |

`docs/decisions/DEC-20240115-CHG-061.yaml` — не `decision.schema.yaml`. Frozen extra принял любой `DEC-*`.

Логи: [runs/S09/r3-frozen/](runs/S09/r3-frozen/).

## Независимо

- Hidden suite: **pass** только r1 (`duplicate` + provenance + нет code/spec).
- r2/r3: **fail** (нет терминального rejected/duplicate на Change).
- Frozen Intake extra «use status continue» не помешал r1 записать `duplicate` в `change.yaml`.
- Промпты не меняли.

## Handoff

- **Готово A09-09:** `done` / `fail`. Дальше [A09-10](../../packets/A09-10.md) (S10 interrupt) с теми же замороженными prompts.
- Не подкручивать Intake под `status: duplicate`. Skills не патчить.
