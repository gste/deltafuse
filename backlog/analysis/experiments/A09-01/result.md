# Результат эксперимента A09-01

- **ID карточки:** A09-01 (дети A09-01a/b/c)
- **Ревизия старта:** `e57dc9d`; исполнение frozen r2: `55411ea`
- **Статус исполнения:** **in-progress** (A09-01a **done** / `partial`; исполняется A09-01b S03)
- **Критерии:** `SPEC-001`, `SPEC-002`, `CODE-001`, `TEST-001`, `PROC-004`, `PROC-007`
- **Вердикт A09-01a:** **partial** — r3/r4/r5 TASK-001 Green + hidden suite pass; 0 Verify; r2 = F-008; F-009 устойчив, отложен в A12. r6 не делали.

## Сплит

До исполнения созданы [A09-01a](../../packets/A09-01a.md) (S02), [A09-01b](../../packets/A09-01b.md) (S03), [A09-01c](../../packets/A09-01c.md) (S04).

## Исторический S02 r1 (thinking on, Studio / F-007)

Протокол `max_tokens: 2048` + thinking: `content` пустой, `finish_reason: length`. Калибровка schema-8k: Intake `CHG-107` прошёл `check_gate(intake)`; Analyze-dump ~30 мин без JSON. Finding: [F-007](../../../findings/F-007.md) — **mitigated** frozen `--reasoning off`.

Логи: [runs/S02/r1/](runs/S02/r1/), [runs/S02/r1-schema-8k/](runs/S02/r1-schema-8k/).

## S02 r2-frozen (`:1240`, thinking off, `max_tokens: 2048`)

Продукт: `work/S02-r2/` (не переиспользовать dirty `S02-r1`). Пакет: `CHG-001-ratelimit-cooldown`. Oracle/hidden_suite в prompt не входили.

| Фаза | Outcome | Попытки | TTFT / elapsed (последняя ok) | `reasoning_chars` | Независимый gate |
|---|---|---|---|---|---|
| Intake | pass | 2 | 7.6 с / 45.5 с | 0 | `check_gate(intake)=[]` |
| Analyze routing | pass | 2 | 17.1 с / 59.1 с | 0 | routing schema `[]`; `analyzed` отложен |
| Analyze slices | blocked-on-decision | 1 (после JSON-fail) | 15.9 с / 40.2 с | 0 | `SLICE-01.md` schema ok; нет DEC-файла |
| Analyze coverage | pass (схема) | 1 | 18.7 с / 38.3 с | 0 | схема ok; `analyzed` fail — 12 orphan claims, [F-008](../../../findings/F-008.md) |

Попытка 1 Intake: нет обязательных `deltas/slices/decisions/tasks` (пустые списки). Попытка 2 — `gate ok`.

Попытка 1 routing: `schema_version` запрещён `routing.schema.yaml` (`additionalProperties: false`). Харнесс сначала считал pass по факту файла; исправлено — routing-only теперь валидирует схему. Попытка 2 сняла `schema_version`. Все claim IDs из `request.md` → `security.ratelimit`.

VRAM ~5370–5450 / 8188 MiB. `usage` в stream **неизвестен**. Studio `:1234` не использовался. После первой серии slices сервер `:1240` упал; перезапущен тем же профилем.

### Analyze slices

Сначала JSON не сходился: ключ `frontmatter` вместо `content`, два path в одном объекте, обрыв при 2048 токенах. Логи: [jsonshape](runs/S02/r2-frozen/analyze-slices-jsonshape/), [2048](runs/S02/r2-frozen/analyze-slices-2048/).

Рабочий вызов: один файл, `max_tokens: 4096`. Записан `SLICE-01.md`, схема зелёная. Модель ответила `blocked-on-decision` из-за U1/U2/U3 и **не записала** `DEC-*.md`. Для однозначного S02 это ложный блок (SPEC-002). В слайсе claims `CR-001..003`, в `request.md` — `O1`/`E1`: покрытие разъедется.

Логи: [runs/S02/r2-frozen/](runs/S02/r2-frozen/). Гейты: [intake](runs/S02/r2-frozen/intake/independent_gate.yaml), [routing](runs/S02/r2-frozen/analyze/independent_gate.yaml), [slices](runs/S02/r2-frozen/analyze-slices/independent_gate.yaml), [coverage](runs/S02/r2-frozen/analyze-coverage/independent_gate.yaml).

### Analyze coverage

Один вызов, `status: continue`, ~38 с. `coverage.yaml` без `schema_version`, все O1…U3 → `SLICE-01`. Схема зелёная.

Specify на пакете r2 не начинать.

## S02 r3-frozen (подсказка харнесса: claims = CR-NNN)

Продукт: `work/S02-r3/`. Oracle в prompt не входил. Skills не менялись.

| Фаза | Outcome | Попытки | TTFT / elapsed | `reasoning_chars` | Независимый gate |
|---|---|---|---|---|---|
| Intake | pass | 1 | 11.0 с / 48.9 с | 0 | `intake=[]`; извлечено CR-001…009 |
| Analyze routing | pass | 2 | 10.0 с / 34.6 с | 0 | схема ok (попытка 1: `schema_version`) |
| Analyze slices | pass | 1 | 14.7 с / 39.3 с | 0 | `SLICE-01` schema ok; `status: continue`; без DEC |
| Analyze coverage | pass | 1 | 16.7 с / 35.4 с | 0 | схема + completeness ok |
| Specify | pass | 1 | 21.5 с / 51.2 с | 0 | `specified=[]`; записаны spec-delta + `ratelimit.md` |
| Decompose | pass | 1 (после 3 fail на paths) | 27.5 с / 98.1 с | 0 | `decomposed=[]`; TASK-001 и TASK-002 |
| Target | pass | 1 | 28.2 с / 38.4 с | 0 | `targeting=[]`; pytest 1 failed / 1 passed; TypeError на `penalty_seconds` |
| Implement TASK-001 | pass | 1 | 28.1 с / 45.4 с | 0 | `implemented=[]`; pytest 2 passed; тесты не трогали |
| Target TASK-002 (1-й, фальшивый Red) | pass-schema | 1 | 33.6 с / 46.2 с | 0 | pytest 1 failed; приватный `_blocked_until`; [F-009](../../../findings/F-009.md) |
| Target TASK-002 (повтор) | already-green | 2 | 32.4 с / 42.4 с | 0 | попытка 1: `._simulate_*` отвергнута; попытка 2: тест lift убран, 2 passed |

Независимый `check_gate(analyzed)` на `CHG-001-ratelimit-cooldown`: **[]**. `analysis.md` skill просит, гейт не требует — файла нет.

Независимый `check_gate(implemented)`: **[]**. Харнесс прогнал pytest: **2 passed**. Тесты не менялись. В `limiter.py`: `penalty_seconds=0.0`, lock на неудачном consume, `is_blocked` пока окно не вышло, auto-lift. TASK-002 `pending`. Implement TASK-002 не запускали: overshoot + фальшивый Red. Hidden suite аудитора (не в prompt): **2 passed**.

GT oracle (после прогона): смысл CR-002+007 ≈ oracle CR-001; CR-003+004 ≈ CR-002; CR-005+006 ≈ CR-003. Лишние CR-001 (observation), CR-008/009 (unknowns) — precision < 0.85 если считать все extracted. Recall GT по смыслу полный. Фиктивного Decision не было (SPEC-002).

Логи: [runs/S02/r3-frozen/](runs/S02/r3-frozen/).

## S02 r4-frozen (чистый `work/S02-r4/`)

Oracle в prompt не входил. Skills не менялись.

| Фаза | Outcome | Попытки | TTFT / elapsed | `reasoning_chars` | Независимый gate |
|---|---|---|---|---|---|
| Intake | pass | 1 | 14.6 с / 59.5 с | 0 | `intake=[]`; CR-001…007 |
| Analyze routing | pass | 3 | 13.2 с / 41.1 с | 0 | схема ok (1: fake Decision; 2: `schema_version`) |
| Analyze slices | pass | 1 | 17.2 с / 46.3 с | 0 | `SLICE-01` schema ok; `continue`; без DEC |
| Analyze coverage | pass | 1 | 19.6 с / 40.2 с | 0 | схема + `analyzed=[]` |
| Specify | pass | 1 | 27.0 с / 56.9 с | 0 | `specified=[]`; default `0.0` в REQ-RL-01 |
| Decompose | pass | 2 | 34.2 с / 132.3 с | 0 | `decomposed=[]`; снова TASK-001+002 |
| Target TASK-001 | pass | 1 | 35.4 с / 49.9 с | 0 | TypeError на `penalty_seconds`; второй тест уже про lock |
| Implement TASK-001 | pass | 1 | 36.0 с / 58.5 с | 0 | pytest 3 passed; lock+lift в коде |
| Target TASK-002 | pass-schema | 1 | 41.7 с / 62.6 с | 0 | pytest 1 failed; `is_blocked False` сразу при окне 60 с — [F-009](../../../findings/F-009.md) |

Implement TASK-002 не запускали. Hidden suite аудитора: **2 passed**.

GT: CR-001≈oracle CR-001; CR-002+003≈CR-002; CR-004+005≈CR-003; CR-006 compat; CR-007 hypothesis. Recall GT по смыслу полный. Precision < 0.85. Фиктивного DEC-файла нет (попытка routing отвергнута харнессом).

Логи: [runs/S02/r4-frozen/](runs/S02/r4-frozen/).

## S02 r5-frozen (чистый `work/S02-r5/`)

Oracle в prompt не входил. Skills не менялись. Харнесс: strip `schema_version` на routing; specify без `added/modified` в frontmatter.

| Фаза | Outcome | Попытки | TTFT / elapsed | `reasoning_chars` | Независимый gate |
|---|---|---|---|---|---|
| Intake | pass | 1 | 14.1 с / 62.5 с | 0 | `intake=[]`; CR-001…009 |
| Analyze routing | pass | 1 (+3 fail до strip) | 13.7 с / 48.5 с | 0 | strip `schema_version`; схема ok |
| Analyze slices | pass | 1 | 19.0 с / 60.1 с | 0 | `SLICE-01`; `continue` |
| Analyze coverage | pass | 1 | 22.8 с / 44.1 с | 0 | `analyzed=[]` |
| Specify | pass | 1 (+3 fail REQ-as-path) | 27.5 с / 54.3 с | 0 | `specified=[]`; default `0.0` в live spec нет |
| Decompose | pass | 2 | 31.4 с / 110.7 с | 0 | TASK-001 read-only + TASK-002 implement |
| Target TASK-001 | pass | 1 | 29.1 с / 38.5 с | 0 | TypeError на `penalty_seconds` |
| Implement TASK-001 | pass | 1 | 29.9 с / 51.4 с | 0 | pytest 2 passed; lock+lift в коде |
| Target TASK-002 | already-green | 1 | 33.9 с / 43.5 с | 0 | тест lift не добавлен; [F-009](../../../findings/F-009.md) vacuous |

Implement TASK-002 не запускали. Hidden suite: **2 passed**.

Логи: [runs/S02/r5-frozen/](runs/S02/r5-frozen/).

## Handoff

- **Готово A09-01a:** три frozen code-прогона (r3–r5). Карточка `done` с verdict `partial`. F-007 mitigated, F-008, F-009 → A12.
- **Дальше:** [A09-01b](../../packets/A09-01b.md) S03 (баг, spec unchanged). Не патчить skills. Не holdout. Не r6 по S02.
- **Калибровка, не фреймворк:** `CR-NNN`; strip `schema_version` на routing; specify без REQ-id в frontmatter; slices 4096; не выдумывать Decision; Target без `._`.
- **Не менять** skills/`integrity.py` без A12.
- **Runtime:** [local-runtime](../local-runtime/README.md).
