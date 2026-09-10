# Покрытие критериев и доказательность (A12-01)

Дата: 2026-09-08. Карточка [A12-01](../packets/A12-01.md). Ревизия старта: `72a80a8`.

Пакетный `backlog/analysis/criteria.md` нет — IDs из [backlog/criteria.md](../../criteria.md). План: [analysis-plan.md §5](../../analysis-plan.md). Статусы: [index.md](../index.md) (`blocked` = 0).

**Слои (не смешивать).** `A01 pass` = критерий *определён*, не «DF соблюдает». `Framework` = контракт/код/юнит (A02–A07). `SUT` = ornith на `:1240` (A09–A10). Mock-успех A08 **не** считается успехом модели.

Вывод SUT только для `ornith-1.5-35b-a3b` Q4_K_M / 8 GB VRAM + RAM experts. n=3 — пилот, не статистика.

---

## 1. Контроль §5 плана

| Требование §5 | Статус | Evidence / ограничение |
|---|---|---|
| Каждая строка критериев: verdict + evidence или not-tested | **закрыто этим файлом** | таблицы §2–3 |
| Каждая lifecycle-фаза: то же | **закрыто** | §4; Verify/Archive на SUT **not-tested** (кроме S11 r1 Verify fail) |
| Bounded context по фазам; mock ≠ model success | **закрыто с fail/not-tested** | F-002/F-003; A09 `usage` пустой; A08-01 real vs mock разделены; A09 = `:1240` |
| Последовательные Changes, межсрез, interrupt, конфликт Changes | **частично** | A04-03/A05-02/A05-04 статически; S05 fail F-010; S11 не довёл серию; S10 interrupt **not-run**; F-006 на SUT **not-run** |
| Точность тестов независимыми дефектами, не coverage | **слойно** | A07-02 framework mutants 100%; A07-03 protocol продукта; ornith hidden cal S02/S03; holdout hidden/fault в основном **not-run**; F-009 |
| Аналоги: версии, источники, цена, отказ | **закрыто** | [comparison.md](comparison.md); живой ранг **not-tested** ([A11-06](../experiments/A11-06/result.md)) |
| Findings ≠ гипотезы; roadmap → владелец | findings/Q **разделены** (§6); roadmap = [A12-03](../packets/A12-03.md), не эта карточка | |
| Анализ возобновим из `backlog/analysis/` | **да** | index + этот файл + result.md; чат не вход |

---

## 2. BASE (A00) и определение критериев (A01)

| ID | Слой определения | Измерение | Вердикт DF | Evidence |
|---|---|---|---|---|
| BASE-001 | A00-01 | ревизия/границы | **pass** (аудит, не качество DF) | [A00-01](../experiments/A00-01/result.md) |
| BASE-002 | A00-02 | карта компонентов | **pass** | [A00-02](../experiments/A00-02/result.md) |
| BASE-003 | A00-03 | pytest baseline | **pass** (91 tests тогда) | [A00-03](../experiments/A00-03/result.md); позже A07-02 91 passed / 8.24s |
| BASE-004 | A00-04 | PS smoke/layout | **pass** | [A00-04](../experiments/A00-04/result.md) |
| BASE-005 | A00-05 | Bash smoke | **fail** F-001 CRLF/hash | [F-001](../../findings/F-001.md) |
| SPEC-001…007 | A01-01 | только дефиниции | *defined* | не использовать как pass продукта |
| CODE-001…007 | A01-02 | то же | *defined* | |
| TEST-001…006 | A01-03 | то же | *defined* | |
| PROC-001…007 | A01-04 | то же | *defined* | PROC-007 порог предварительный |

---

## 3. Критерии A01 — framework vs SUT

### SPEC

| ID | Framework | SUT ornith | Finding / гипотеза | Evidence |
|---|---|---|---|---|
| SPEC-001 | **pass** цепочка A04-01 | **fail** holdout (F-010: specified без live paths; claims не в `docs/spec`) | F-010 | A04-01; A09-13; A09-02/03 |
| SPEC-002 | **pass** ANA-02, AB-06 | **pass** S04 3/3 DEC; **fail** S06 ложный DEC; S09 r2/r3 нет terminal | F- нет отдельного; поведение S06 | A09-01c; A09-04; A09-09; [ablation AB-06](ablation.md) |
| SPEC-003 | **pass** A04-02 RFC 2119 в контракте | **not-tested** Ratio(Normative) на ornith spec | PP-03 сохранить; EARS исследовать | A04-02; A11-05 |
| SPEC-004 | **pass** A04-02 oracle в TASK | **partial**: cal S02/S03 Red; holdout мало Target; F-009 vacuous | F-009 | A04-02; A09-01; A07-03 |
| SPEC-005 | **pass** DAG A05-02; catalog A02 | **fail** S05 1 slice vs ≥2 (harness extra); S07 Analyze | AB-02; не F | A05-02; A09-03; A10-02 |
| SPEC-006 | **pass** layout A02-10, A06-02 | **fail** F-010: delta/gate без записи live spec | F-010 | A02-10; A06-02; A09-02+ |
| SPEC-007 | **pass** A04-03 stale anchors | **not-tested** полная серия S11; F-006 на SUT not-run | F-006 (статика A05-04) | A04-03; A05-04; A09-11 |

### CODE

| ID | Framework | SUT ornith | Finding / гипотеза | Evidence |
|---|---|---|---|---|
| CODE-001 | **pass** A02-07, A06 | **partial** cal S02/S03 Green; holdout почти нет кода | F-010 стоп до Implement | A09-01; A09-13 |
| CODE-002 | **pass** A06-05 paths; **fail** F-002/F-004 enforcement | **not-tested** allowed_paths на holdout diff | F-002, F-004 | A03-02; A06-05 |
| CODE-003 | **pass** VER regression schema | **not-tested** (Verify почти not-run) | — | A02-08; A09-13 |
| CODE-004 | контракт TASK scope | **not-tested** продукт; A10-01 SDD gold-plating не DF | — | A10-01 |
| CODE-005 | **pass** A06-01 | **not-tested** продукт | — | A06-01 |
| CODE-006 | **fail** F-004 silent/traversal; **pass** A06-01 модули | **not-tested** как product bug | F-004 | A03-02; A06-01 |
| CODE-007 | **pass** границы A06-01 | **not-tested** radon на продукт | — | A06-01 |

### TEST

| ID | Framework | SUT ornith | Finding / гипотеза | Evidence |
|---|---|---|---|---|
| TEST-001 | **pass** A07-02 T1–T8 100% | **partial** hidden cal S02/S03; holdout hidden/fault **not-run**; F-009 | F-009 | A07-02; A07-03; A09-13 |
| TEST-002 | **pass** A07-02 black-box | **fail** F-009 private/overshoot | F-009 | A09-01a |
| TEST-003 | **pass** A07-02 FAR=0 | **not-tested** продукт FDR/RRR A07-03 не гоняли на holdout | — | A07-03 protocol |
| TEST-004 | **pass** A07-01 T1/T2 schema | **fail** F-009; S08b already-green | F-009 | A07-01; A09-07 |
| TEST-005 | **pass** A07-02 91/8.24s | **not-tested** flaky продукт; F-006 concurrent evidence | F-006 | A05-04; A07-02 |
| TEST-006 | **pass** A07-02 <30s | **not-tested** product suite latency | — | A07-02 |

### PROC

| ID | Framework | SUT ornith | Finding / гипотеза | Evidence |
|---|---|---|---|---|
| PROC-001 | **pass** A02-08 VER, A06-02 | **fail** F-010 provenance «specified» ≠ live spec | F-010 | A06-02; A09-13 |
| PROC-002 | **fail** F-005 cancelled/superseded vs `converged`; иначе T-гейты **pass** | S09 r1 duplicate **pass**; r2/r3 fail; S10 interrupt **not-run** | F-005 | A05-01; A02-09; A09-09 |
| PROC-003 | **pass** A05-03, A06-03/04 | S10 interrupt **not-run** | — | A09-10; A05-03 |
| PROC-004 | **fail** F-002, F-003 | `usage` tokens **not-tested**; furrow = harness Q-001 | F-002, F-003; Q-001/Q-002 | A03-01; A09-13 |
| PROC-005 | **pass** A05-03 max retries | A09 halt после 3 retry **соблюдён** | — | protocol §4; A09 |
| PROC-006 | **pass** A02-09, AB-06 | S04 3/3; S12 не auto-accept | — | A09-01c; A09-12 |
| PROC-007 | **partial**: VRAM ~4.2–5.5/8.2 GiB; elapsed обычно <120 с; Decompose до 147 с; CLI RAM 512 MB **not-tested**; GPU-only 8 GB **не** доказан (веса ~20 GiB RAM) | то же | Q-001 latency | [local-results](local-results.md) |

---

## 4. Lifecycle-фазы

Контракт семи фаз: [A02-02…A02-08](../experiments/A02-08/result.md) → [contracts.md](../../matrices/contracts.md).

| Фаза | Framework | SUT (A09-13) | Примечание |
|---|---|---|---|
| Intake | **pass** A02-02 | **pass** диапазон; S12 authority pass | |
| Route / Analyze | **pass** A02-03; **fail** F-008 claims | routing измерен; S07 стоп | F-008 |
| Specify | **pass** A02-04 схема; **fail** F-010 гейт | cal S02/S03 pass (extras); holdout **fail** | главный стоп |
| Decompose | **pass** A02-05 | cal + часть holdout; schema fails | |
| Target | **pass** A02-06; **fail** F-009 на cal | holdout редко | |
| Implement | **pass** A02-07 | cal S02/S03; holdout мало | |
| Verify | **pass** A02-08 схема | почти **not-run**; S11 r1 **fail** | |
| Converge / Archive | **pass** A02-08; **fail** F-005 vs schema | **not-run** на ornith | 0 `converged` |

---

## 5. Сценарии S01–S12 (план §5: рассмотрены)

| Case | Подготовка A08 | Измерение A09 | Доказательность для A12-02 |
|---|---|---|---|
| S01 | pass | fail F-010 | bootstrap на SUT не закрыт |
| S02 | pass | partial F-008/F-009; 0 Verify | tiny code возможен с extras |
| S03 | pass | pass Implement; 0 Verify | bugfix cal |
| S04 | pass | pass DEC | Human gate держится |
| S05 | pass | fail F-010 | multi-cap не закрыт; A10-02 extra ≠ live spec |
| S06 | pass | fail ложный DEC / F-010 | лестница размера **not-run** |
| S07 | pass | fail Analyze | крупный каталог не закрыт |
| S08a | pass | fail spec unchanged | refactor не закрыт |
| S08b | pass | fail; Q-005 | docs-only |
| S08c | pass | fail ops unchanged | ops |
| S09 | pass | fail 2/3 terminal | r1 duplicate ok |
| S10 | pass | fail Specify; interrupt **not-run** | PROC-003 SUT gap |
| S11 | pass | fail; F-006 **not-run** | серия Changes SUT gap |
| S12 | pass | fail Specify; intake authority pass | forged Green **not-run** |

A10-01 SDD vs DF: **не** успех аналога; homemade SDD, тот же SUT. A11-06 analog products **not-tested**.

---

## 6. Findings vs гипотезы vs mitigated

Не считать Q-* доказанным дефектом. Не считать F-007 текущим блокером SUT (`--reasoning off`).

| ID | Тип | Суть | Слой | A12 |
|---|---|---|---|---|
| F-001 | defect | CRLF / lock hash | framework | P1 PP-07 |
| F-002 | limitation | `PHASE_CONTRACTS` мёртв; нет task budget | framework | P1; не практика A11-05 |
| F-003 | defect | `words * 1.3` | framework | P1 → Q-002 |
| F-004 | defect | path traversal / silent skip | framework | P0 CODE-006; PP-09 |
| F-005 | defect | `cancelled`/`superseded` ≠ terminal `converged` | framework | P1; PP-08; SUT not-run |
| F-006 | defect | stale evidence silent pass | framework | P0; SUT not-run |
| F-007 | defect | thinking eats 2048 | Studio SUT | **mitigated** на `:1240` |
| F-008 | defect | analyzed только CR-* | SUT+gate | P1 |
| F-009 | defect | fake Red / private | SUT Target | P0 TEST-004 |
| F-010 | defect | `specified` без live spec | framework+SUT | P0; AB-01 |

Гипотезы (parking, не findings): Q-001 furrow; Q-002 tokenizer; Q-003 embeddings; Q-004 reject-кандидат; Q-005 docs-only; Q-006 ops files; Q-007 constitution-lock; Q-008 post-Verify spec-delta.

Дубли: много A09 карточек → один F-010. AB-01 = то же. Не плодить F-011 из A11.

Противоречия, сведённые к слоям:

1. A02-08 VER-01 «только implemented/verified» vs schema `cancelled`/`superseded` → **F-005**, не ошибка A02-08 (гейт как код).
2. A07-01 TEST-004 pass vs F-009 → schema evidence ≠ поведение модели.
3. A04-03 SPEC-007 pass vs A09-11 fail → статический oracle ≠ holdout серии.
4. A05-02 cross-slice на Converge vs S05 не дошёл до Verify → контракт есть, SUT не упражнял.
5. Analog «лучше DF» **запрещён**: нет той же интеграции (A11-06).

---

## 7. Blocked и not-tested (не скрыты)

| Пробел | Почему не blocked карточки | Условие закрытия |
|---|---|---|
| Живой ранг Spec Kit/OpenSpec/BMAD/Kiro | план A11: контракты если нет той же интеграции | first-class `:1240` |
| Verify/Archive на ornith | holdout стоп на Specify | после фикса F-010 |
| Interrupt S10 | Specify 3/3 | тот же |
| F-006 на SUT | S11 не converged | тот же + два Change |
| A09 `usage` tokens | harness пустой объект | чинить телеметрию, не F-003 |
| analog CLI install | сознательно не ставили | не нужно для A12-02 |
| n>3 / другие модели | вне скоупа SUT | не обобщать |

Очередь: `blocked` карточек **нет**. A12-02/03/04 `planned`.
