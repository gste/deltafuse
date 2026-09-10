# DeltaFuse vs минимальный SDD (A10-01)

Дата: 2026-09-08. Ревизия DF-руки: A09 закрыт `8f05314`. SDD-рука: тот же SUT `:1240`, `input.md` S02/S05, oracle не в prompt.

**Минимальный SDD:** spec → TASK.md → test/code → review (pytest `tests/`). JSON `files[]` как у A09, без skills/FSM/Change-пакета.

n = 3 на case. Не статистика. DF S02 — калибровка **с extras**; DF S05 — holdout **без** extras. SDD extras не имел.

## Tiny fix (S02)

| | DeltaFuse (A09-01a r3–r5) | SDD |
|---|---|---|
| Вердикт карточки | partial | 1/3 hidden pass (r1); r2/r3 hidden fail |
| Дошло до кода | да, TASK-001 Green | 3/3 `penalty_seconds` в limiter |
| Hidden suite | 2 passed | r1: 2 passed; r2/r3: 1 fail (lock timing) |
| Verify / converged | not-run | нет FSM |
| Вызовов LLM (порядок) | ~10–12 фаз с Analyze-split | 5–6 |
| Prompt spec/implement | skill + extras | ~5–9k chars |
| Файлы сверх кода/spec | Change YAML, routing, coverage, slices, tasks | TASK.md |
| Intent | recall по смыслу; precision CR-* < 0.85 | spec с penalty MUST |
| Human | extras заранее | 0 в прогоне |
| F-009 | да (TASK-002) | r3: pytest green / hidden fail |

## Cross-capability (S05)

| | DeltaFuse (A09-03) | SDD |
|---|---|---|
| Вердикт | fail, Specify / F-010 | fail, review pytest |
| Spec `usage_stats` / `rate_policy` | нет | 3/3 оба файла |
| Код `get_stats` / policy | нет | 3/3 |
| Integration tests | нет | 3/3 файл есть |
| pytest продукта | not-run | 3/3 fail (2–3 теста) |
| Hidden slice ≥2 | not-run | **not-applicable** (нет slices) |
| Вызовов | Intake+Analyze+Specify fail | 6–7 |
| Implement elapsed | — | ~128–149 с / шаг |

SDD на S05 **дальше** (есть spec и код). Это не качество: тесты модели красные, catalog r1 без `rate_policy`. Дешёвый прогресс ≠ улучшение, пока hidden/pytest красные.

## Механизм → дефект → цена → решение (черновик для A10-02)

| Механизм | Что предотвратил на этой паре | Цена | Решение |
|---|---|---|---|
| `specified` + spec-delta schema | На S05 holdout — почти ничего полезного; стоп на YAML | 3 retry Specify, нет кода | **исследовать** в A10-02; не считать обязательным ядром, пока F-010 |
| routing + frozen 1× SLICE-01 | На S05 не дал 2 capability | лишний RTT; оракул ≥2 срезов | **упростить/удалить extra**; routing как подсказка — A10-02 |
| coverage.yaml / change.yaml | provenance, если пакет живой | много полей, schema fail | **сохранить своё** для аудита; не блокировать код holdout этим |
| Target Red | DF S02 F-009; SDD r3 ложный green своих тестов | 1–2 вызова | **сохранить** независимый hidden; не доверять только pytest агента |
| Human Decision gate | ни одна рука не auto-accept | — | **сохранить** |
| Минимальный SDD | S05: файлы spec/code появились | нет FSM-доказательства, слабый review | **не переносить** как замену ядра; годится как нижняя планка сравнения |

## not-tested

- Ablation одного фактора (A10-02).
- DF S02 без калибровочных extras.
- Mutation score, Verify, n>3.
- Другие модели.
