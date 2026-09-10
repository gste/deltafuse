# Регресс RM-* после A12-03

Дата: 2026-09-09. Реализация: ветка `feature/2026-09-06-review`, последний пункт `RM-031` (`e82bc17`). Очередь: [A13](index.md). Карточки: [A13-01](packets/A13-01.md) … [A13-04](packets/A13-04.md).

Это **проверка уже принятых фиксов**, не новый аудит и не очередь ornith в `llm-optimization`.

SUT живого слоя — тот же, что A09: ornith `:1240`, `--reasoning off`, `--cpu-moe`. Контрактный слой — pytest без модели. Нет процесса на `:1240` → живые карточки `blocked`, R0 всё равно гонять.

## Зачем

Контрактные тесты закрыли acceptance каждого RM на фикстурах. A09 holdout падал на ложных гейтах (F-010, F-009) **до** этих патчей. Пока ornith не прогнан на том же харнессе, нельзя сказать, что P0 чинит продукт на модели, а не только `check_gate`.

Два слоя, не смешивать вердикты:

| Слой | Что доказывает | Что не доказывает |
|---|---|---|
| R0 контракт | гейт/схема/skill делают заявленное на диске | ornith напишет live spec |
| R1–R3 SUT | модель + новые skills/гейты на holdout | другие модели, analog, GPU-only 8 GB |

## Порядок

```text
R0  A13-01  pytest + smoke + layout     без LLM
R1  A13-02  P0 holdout на ornith        S05, S01, S02, S04
R2  A13-03  P1/P2 на ornith             S03, S08b, S08c, S05 slices
R3  A13-04  неизвестные A12             S10, S11, Verify — optional
```

Не начинать R1, пока R0 красный. Не начинать полный A09 11/11, пока R1 не показал, что F-010 больше не даёт vacuous `specified`. n=1 на case в R1/R2 (пилот). n=3 — только если R1 `fail` спорный.

Харнесс: `python backlog/analysis/experiments/A09-01/harness/run_case.py`. Skills брать из `process/skills/**` текущей ветки (не frozen A09 snapshot). Калибровочные extras S02 «только SLICE-01» **не** возвращать. `A09_ANALYZE_FOCUS`: сначала `routing`, затем slices/coverage (RM-020). Oracle/hidden/fault **не** в prompt.

## R0 — контракт (A13-01)

```powershell
python -m pytest tests/unit tests/integration tests/e2e tests/evals -q --tb=short
tests/smoke-test.ps1
# если есть bash: tests/smoke-test.sh
```

Ожидание: pytest зелёный; PBT-тест RM-031 может быть `skipped` (нет Hypothesis) — это pass плана, не fail.

Карта RM → уже существующие тесты (регресс «не сломали»):

| RM | Finding / Q | Тест-якорь |
|---|---|---|
| 001 | F-001 | `.gitattributes`; smoke `.sh` LF |
| 004 | F-004 | path traversal в integrity/context |
| 010 | F-010 | `test_specified_rejects_missing_*` |
| 009 | F-009 | `test_targeting_accepts_already_green`, `test_targeting_rejects_private_red_test` |
| 006 | F-006 | `test_implemented_rejects_stale_green_after_spec_change` |
| 002 | F-002 | `test_decomposed_rejects_task_without_budget`, PHASE_CONTRACTS |
| 003 | F-003 | upper-bound YAML/code/RU в `test_context.py` |
| 005 | F-005 | `test_converged_accepts_cancelled_and_superseded_tasks` |
| 008 | Q-008 | `test_converged_rejects_wiped_added_spec_after_specify` |
| 018 | F-008 | `test_analyzed_accepts_o1_e1_claims` |
| 020 | Q-001 | `test_narrow_analyze_gate_after_full_set`, Human Gate |
| 021 | Q-005/006 | `test_docs_route_*`, `test_ops_route_*`, `test_code_route_still_requires_regression` |
| 022 | AB-02/05 | `test_analyzed_ignores_routing_top_level_unknown_keys`, `test_two_slices_do_not_satisfy_specified_without_live_spec` |
| 030 | AB-04 | `test_analyzed_does_not_require_analysis_md` |
| 031 | PP-04/KI-07 | `tests/unit/test_spec_style.py` |

R0 `fail` → чинить контракт, не орнита.

## R1 — P0 на ornith (A13-02)

Цель: стоп-дефекты A09 больше не дают ложный pass.

| Case | Был (A09) | После RM ожидание |
|---|---|---|
| **S05** Specify | `specified` без `usage_stats.md` / `rate_policy.md` (F-010) | `specified` **fail**, пока нет live файлов; pass только с записанными модулями |
| **S01** пустой продукт | vacuous specify | то же: нет catalog/live spec → не `specified` |
| **S02** Declare TASK-002 | фиктивный Red / `_private` (F-009) | `already-green` или halt; не `expected-failure` на private |
| **S04** Decision | 3/3 `blocked-on-decision` | **сохранить** стоп; агент не auto-accept |

Hidden suite по-прежнему не в prompt. Если свои тесты модели зелёные, а hidden красный — это fail продукта, не skip.

S05: два slice-файла (RM-022) **не** заменяют live spec.

Нет `:1240` → `blocked`. Не подменять облаком. Не Studio `:1234`.

## R2 — маршруты и Analyze (A13-03)

Только после R1: иначе снова измеряем F-010.

| Case | RM | Ожидание |
|---|---|---|
| S03 bugfix | 010, 009 | `requirement_delta: none` + живые якоря; authentic Red; spec не портить |
| S08b docs | 021 | `route: docs`; нет правки `limiter.py`; Specify всё ещё live spec |
| S08c ops | 021 | ops-файлы; не product pytest; Specify не пишет deploy YAML вместо spec |
| S05 Analyze | 020, 022, 030 | routing первым; ≥2 slices без extra «только SLICE-01»; лишний `schema_version` на routing не валит `analyzed`; без `analysis.md` ок |
| S02 Analyze | 018, 020 | O1/E1 не теряются; `call_width` не снимает Specify |

Code Change (S02/S03) не должен пройти Implement без regression. Docs/ops не должны требовать product pytest.

## R3 — неизвестные A12 (A13-04, не блокер merge контракта)

Делать, если R1–R2 зелёные или явно `partial` с причиной. Не раздувать в обязательный гейт ветки.

| Тема | Зачем | Skip если |
|---|---|---|
| Verify / Archive S02 или S03 | A09: 0 `converged` | R1 не дошёл до Declare |
| S10 interrupt | PROC-003 на SUT | нет времени на рестарт mid-phase |
| S11 два Change | F-006 на серии, не только yaml hash | R1 F-006 контракт уже есть |
| Analog live `:1240` | A11-06 not-tested | **не в этой очереди** (ядро не заменять) |

## Не делать в A13

- Повтор полного A09 11/11 до закрытия R1.
- Патч A09 extras / `run_ablate.py` «чтобы модель прошла».
- Кролики и префилл ornith — другой объект (runtime llama-server в `llm-optimization`, не гейты DF).
- Новые RM «заодно». Finding только если регресс воспроизводим.
- `git push`. Облако вместо ornith. Снятие Human Gate / hidden suite.

## Вердикт очереди

| Исход | Когда |
|---|---|
| `pass` | R0 зелёный; R1 S05 больше не vacuous specified; S04 по-прежнему Human Gate |
| `partial` | R0 зелёный; `:1240` blocked или R1 n=1 с оговоркой |
| `fail` | R0 красный **или** S05 снова `specified` без live spec **или** S04 auto-accept |

Handoff: `experiments/A13-0N/result.md`. Обновлять только [index.md](index.md).
