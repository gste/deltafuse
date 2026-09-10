# Результат эксперимента A09-05

- **ID карточки:** A09-05
- **Ревизия старта:** `b6d2156`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-004`, `PROC-004`, `CODE-001`
- **Вердикт:** **fail** — 0/3 не дошли до Specify. Prompts по holdout **не** подкручивали.

Holdout S07 (15 capabilities в каталоге, новая `infra.distributed_ratelimit`). Frozen `:1240`. Калибровочные extras S02/S03/S04 в prompt не входили. Oracle/hidden_suite в prompt не входили. Seed: stubs 14 capability + живой `security.ratelimit`.

Это первый A09-holdout, который остановился на Analyze, не на Specify.

Routing-first не прикладывает тела stub-spec; slices/coverage frozen `phase_context` кладёт `billing/*` и `api.pagination.md` в prompt (скрытое полное чтение каталога со стороны харнесса, не модели).

## S07 r1-frozen (`work/S07-r1/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 2 | 8.7 с / 43.7 с | JSON parse на 1-й |
| Analyze routing | pass | 2 | 11.4 с / 35.8 с | все CR → `infra.distributed_ratelimit` |
| Analyze slices | pass | 2 | 23.0 с / 43.9 с | 1 срез (оракул 1–3) |
| Analyze coverage | fail | 3 | 25.4 с / 47.8 с | extra keys + schema_version |

Specify не запускали. `prompt_chars` coverage ~21–25k.

Логи: [runs/S07/r1-frozen/](runs/S07/r1-frozen/).

## S07 r2-frozen (`work/S07-r2/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 12.0 с / 49.7 с | CR-* |
| Analyze routing | pass | 1 | 15.4 с / 43.8 с | смешанные primary (`config_reload` / `health_check`) |
| Analyze slices | fail | 3 | 0.2 с / 31.9 с | schema `slice_id` / status `continue`; JSON parse ×2 |

Логи: [runs/S07/r2-frozen/](runs/S07/r2-frozen/).

## S07 r3-frozen (`work/S07-r3/`)

| Фаза | Outcome | Попытки | TTFT / elapsed | Независимый gate |
|---|---|---|---|---|
| Intake | pass | 1 | 11.9 с / 52.8 с | CR-* |
| Analyze routing | pass | 1 | 15.4 с / 48.5 с | все CR → `infra.distributed_ratelimit` |
| Analyze slices | fail | 3 | 24.0 с / 47.6 с | нет `title`; status `continue` |

Логи: [runs/S07/r3-frozen/](runs/S07/r3-frozen/).

## Независимо

- Hidden suite: **not-run** (нет кода distributed).
- `docs/spec/infra/distributed_ratelimit.md`: нет.
- Frozen Analyze extra по-прежнему один `SLICE-01`.
- Промпты не меняли. Лимит `readable[:24]` не трогали.

## Handoff

- **Готово A09-05:** `done` / `fail`. Дальше [A09-06](../../packets/A09-06.md) (S08a refactoring) с теми же замороженными prompts.
- Не подкручивать slices/coverage под каталог из 15. Skills не патчить.
- Дамп unrelated spec после routing — наблюдение для A12 (контракт «route before loading detailed spec» vs frozen harness).
