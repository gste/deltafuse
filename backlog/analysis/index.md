# Очередь анализа DeltaFuse

Дата обновления: 2026-09-10.

- **Статус:** `done` — A13 закрыта, вердикт очереди `partial`.
- **Текущая задача аудита:** нет.
- **Следующая задача:** нет.
- **Счётчики:** всего 88; `planned` 0; `in-progress` 0; `done` 88; `blocked` 0.

План регресса: [regression-plan.md](regression-plan.md). Не смешивать с `backlog/llm-optimization-v2/`.

- **Локальная модель:** `ornith-1.5-35b-a3b` Q4_K_M, голый llama-server `:1240`, `--reasoning off`, `--cpu-moe` — [local-runtime](experiments/local-runtime/README.md). Исторический Studio-снимок: [A03-03](experiments/A03-03/profile.md).

[План](../analysis-plan.md) · [Правила исполнения](README.md) · [Проверка плана](plan-review.md)

Это статус очереди аудита в backlog, а не состояние lifecycle продукта или фреймворка. Статусы вести только здесь. Поле evidence заполнять по факту выполнения; «—» означает отсутствие результата.

Начальный маршрут: **A00-01 → A00-02 → A00-03/04/05 → A01-01/02/03/04 → A02-01 → A03-03 → A03-01 → A03-02/04/05** с учётом зависимостей строк. Затем продолжить A02-02 и остальные пакеты. Задачи, которым не нужен недоступный runtime, можно выполнять при аппаратной блокировке.

Отдельная задача анализа локальной LLM: **[A03-04](packets/A03-04.md)**; подготовка профиля: [A03-03](packets/A03-03.md); реальные сквозные измерения: [A09-01](packets/A09-01.md) и последующие A09.

## A00

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A00-01 — Зафиксировать ревизию и границы аудита](packets/A00-01.md) | — | done | [BASE-001: pass; результат и handoff](experiments/A00-01/result.md) |
| [A00-02 — Составить карту компонентов](packets/A00-02.md) | A00-01 | done | [BASE-002: pass; карта и handoff](experiments/A00-02/result.md) |
| [A00-03 — Записать исходный результат pytest](packets/A00-03.md) | A00-02 | done | [BASE-003: pass; результат](experiments/A00-03/result.md) |
| [A00-04 — Проверить PowerShell smoke и layout](packets/A00-04.md) | A00-02 | done | [BASE-004: pass; результат и handoff](experiments/A00-04/result.md) |
| [A00-05 — Проверить Bash smoke и layout](packets/A00-05.md) | A00-02 | done | [BASE-005: pass; результат, handoff](experiments/A00-05/result.md), [F-001](../findings/F-001.md) |

## A01

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A01-01 — Опредерить критерии качества спецификации](packets/A01-01.md) | A00-03, A00-04, A00-05 | done | [SPEC-001..007: pass; результат и handoff](experiments/A01-01/result.md) |
| [A01-02 — Опредерить критерии качества кода](packets/A01-02.md) | A00-03, A00-04, A00-05 | done | [CODE-001..007: pass; результат и handoff](experiments/A01-02/result.md) |
| [A01-03 — Опредерить критерии полезности тестов](packets/A01-03.md) | A00-03, A00-04, A00-05 | done | [TEST-001..006: pass; результат и handoff](experiments/A01-03/result.md) |
| [A01-04 — Опредерить критерии процесса и ресурсов](packets/A01-04.md) | A00-03, A00-04, A00-05 | done | [PROC-001..007: pass; результат и handoff](experiments/A01-04/result.md) |

## A02

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A02-01 — Сопоставить контракт ограничения контекста](packets/A02-01.md) | A01-01, A01-02, A01-03, A01-04 | done | [pass; contracts.md, F-002; результат](experiments/A02-01/result.md), [F-002](../findings/F-002.md) |
| [A02-02 — Проверить контракт Intake](packets/A02-02.md) | A02-01 | done | [INT-01..06: pass; contracts.md, результат](experiments/A02-02/result.md) |
| [A02-03 — Проверить контракт Route and Analyze](packets/A02-03.md) | A02-01 | done | [ANA-01..06: pass; contracts.md, результат](experiments/A02-03/result.md) |
| [A02-04 — Проверить контракт Specify](packets/A02-04.md) | A02-01 | done | [SPC-01..06: pass; contracts.md, результат](experiments/A02-04/result.md) |
| [A02-05 — Проверить контракт Decompose](packets/A02-05.md) | A02-01 | done | [DEC-01..06: pass; contracts.md, результат](experiments/A02-05/result.md) |
| [A02-06 — Проверить контракт Target](packets/A02-06.md) | A02-01 | done | [TAR-01..06: pass; contracts.md, результат](experiments/A02-06/result.md) |
| [A02-07 — Проверить контракт Implement](packets/A02-07.md) | A02-01 | done | [IMP-01..06: pass; contracts.md, результат](experiments/A02-07/result.md) |
| [A02-08 — Проверить контракт Verify, Converge and Archive](packets/A02-08.md) | A02-01 | done | [VER-01..06: pass; contracts.md, результат](experiments/A02-08/result.md) |
| [A02-09 — Проверить обходы gate и terminal paths](packets/A02-09.md) | A02-02, A02-03, A02-04, A02-05, A02-06, A02-07, A02-08 | done | [BYP-01..07: pass; contracts.md, результат](experiments/A02-09/result.md) |
| [A02-10 — Сверить RU/EN, CLI и инструкции установки](packets/A02-10.md) | A02-09 | done | [PROC-001, PROC-006, SPEC-006: pass; contracts.md, результат](experiments/A02-10/result.md) |


## A03

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A03-01 — Проверить фактический prompt и подсчёт токенов](packets/A03-01.md) | A02-01, A03-03 | done | [PROC-004, PROC-007: fail; F-003; результат](experiments/A03-01/result.md), [F-003](../findings/F-003.md) |
| [A03-02 — Проверить отказы и границы чтения](packets/A03-02.md) | A03-01 | done | [PROC-004, CODE-006: fail; F-004; результат](experiments/A03-02/result.md), [F-004](../findings/F-004.md) |
| [A03-03 — Зафиксировать профиль ornith в LM Studio](packets/A03-03.md) | A02-01 | done | [PROC-004, PROC-007: pass; profile.md, результат](experiments/A03-03/result.md) |
| [A03-04 — Проанализировать контракт DeltaFuse локальной LLM](packets/A03-04.md) | A03-03, A03-01, A02-01 | done | [PROC-004, SPEC-007: pass; model_output.md, результат](experiments/A03-04/result.md) |
| [A03-05 — Описать bounded execution каждой фазы](packets/A03-05.md) | A03-02, A03-03 | done | [PROC-004, PROC-005, PROC-007: pass; context-boundaries.md, результат](experiments/A03-05/result.md) |

## A04

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A04-01 — Проследить claims до принятой spec](packets/A04-01.md) | A02-10, A03-04, A03-05 | done | [PROC-001, SPEC-001, SPEC-002: pass; результат](experiments/A04-01/result.md) |
| [A04-02 — Проверить достаточность spec и перенос Decision](packets/A04-02.md) | A04-01 | done | [SPEC-003, SPEC-004, PROC-006: pass; результат](experiments/A04-02/result.md) |
| [A04-03 — Проверить актуальность spec после серии изменений](packets/A04-03.md) | A04-02 | done | [SPEC-005, SPEC-007, PROC-001: pass; результат](experiments/A04-03/result.md) |
| [A04-04 — Проверить bootstrap и baseline существующего кода](packets/A04-04.md) | A04-02 | done | [SPEC-001, SPEC-004, PROC-001: pass; результат](experiments/A04-04/result.md) |

## A05

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A05-01 — Проверить атомарность task и достижимость Red](packets/A05-01.md) | A04-03, A04-04 | done | [PROC-002, TEST-004, CODE-001: fail; F-005; результат](experiments/A05-01/result.md), [F-005](../findings/F-005.md) |
| [A05-02 — Проверить DAG и межсрезовую совместимость](packets/A05-02.md) | A05-01 | done | [PROC-002, TEST-001, SPEC-005: pass; результат](experiments/A05-02/result.md) |
| [A05-03 — Проверить стоимость reconciliation и возобновление](packets/A05-03.md) | A05-02 | done | [PROC-003, PROC-005, PROC-007: pass; результат](experiments/A05-03/result.md) |
| [A05-04 — Проверить конфликт двух Changes над общей spec](packets/A05-04.md) | A05-02 | done | [SPEC-007, TEST-005, PROC-002: fail; F-006; результат](experiments/A05-04/result.md), [F-006](../findings/F-006.md) |

## A06

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A06-01 — Проверить границы модулей и источники правил](packets/A06-01.md) | A02-10 | done | [CODE-005, CODE-006, PROC-002: pass; результат и handoff](experiments/A06-01/result.md) |
| [A06-02 — Проверить установку, пакет и pin/lock/hash](packets/A06-02.md) | A06-01 | done | [SPEC-006, PROC-001, PROC-003: pass; результат и handoff](experiments/A06-02/result.md) |
| [A06-03 — Проверить upgrade и восстановление записи](packets/A06-03.md) | A06-02 | done | [SPEC-006, PROC-001, PROC-003: pass; результат и handoff](experiments/A06-03/result.md) |
| [A06-04 — Проверить archive после прерывания](packets/A06-04.md) | A06-01 | done | [PROC-002, PROC-003, PROC-001: pass; результат и handoff](experiments/A06-04/result.md) |
| [A06-05 — Проверить filesystem и границы полномочий](packets/A06-05.md) | A06-02 | done | [PROC-006, CODE-002, PROC-003: pass; результат и handoff](experiments/A06-05/result.md) |

## A07

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A07-01 — Проверить достоверность Red/Green evidence](packets/A07-01.md) | A01-01, A01-02, A01-03, A01-04, A02-10 | done | [TEST-001, TEST-004, PROC-002: pass; результат и handoff](experiments/A07-01/result.md) |
| [A07-02 — Измерить полезность тестов фреймворка](packets/A07-02.md) | A07-01 | done | [TEST-001, TEST-002, TEST-003, TEST-005, TEST-006: pass; результат и handoff](experiments/A07-02/result.md) |
| [A07-03 — Определить oracle полезности тестов продукта](packets/A07-03.md) | A07-01 | done | [TEST-001, TEST-002, TEST-003, TEST-004, TEST-006: pass; результат и handoff](experiments/A07-03/result.md) |

## A08

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A08-01 — Проверить eval harness и локальный provider](packets/A08-01.md) | A03-04, A03-05, A04-03, A04-04, A05-03, A05-04, A06-03, A06-04, A06-05, A07-02, A07-03 | done | [PROC-004, PROC-007, TEST-001: pass; результат и handoff](experiments/A08-01/result.md) |
| [A08-02 — Зафиксировать calibration/holdout и протокол](packets/A08-02.md) | A08-01 | done | [SPEC-001, SPEC-002, CODE-001, TEST-001, PROC-004: pass; результат и handoff](experiments/A08-02/result.md) |
| [A08-03 — Подготовить S01: Пустой продукт и новая capability](packets/A08-03.md) | A08-02 | done | [SPEC-001, SPEC-004, CODE-001, TEST-001: pass; результат и handoff](experiments/A08-03/result.md) |
| [A08-04 — Подготовить S02: Малое изменение capability](packets/A08-04.md) | A08-02 | done | [SPEC-001, SPEC-006, CODE-002, CODE-003, TEST-001: pass; результат и handoff](experiments/A08-04/result.md) |
| [A08-05 — Подготовить S03: Баг при корректной spec](packets/A08-05.md) | A08-02 | done | [SPEC-001, SPEC-006, CODE-001, TEST-001: pass; результат и handoff](experiments/A08-05/result.md) |
| [A08-06 — Подготовить S04: Неоднозначный запрос и Decision](packets/A08-06.md) | A08-02 | done | [SPEC-001, SPEC-002, PROC-002, PROC-006: pass; результат и handoff](experiments/A08-06/result.md) |
| [A08-07 — Подготовить S05: Несколько capabilities и policy](packets/A08-07.md) | A08-02 | done | [SPEC-001, SPEC-005, CODE-002, CODE-003, TEST-001: pass; результат и handoff](experiments/A08-07/result.md) |
| [A08-08 — Подготовить S06: Длинный raw input](packets/A08-08.md) | A08-02 | done | [SPEC-001, SPEC-003, PROC-004, TEST-001: pass; результат и handoff](experiments/A08-08/result.md) |
| [A08-09 — Подготовить S07: Большой каталог и capability](packets/A08-09.md) | A08-02 | done | [SPEC-001, SPEC-004, PROC-004, CODE-001: pass; результат и handoff](experiments/A08-09/result.md) |
| [A08-10 — Подготовить S08a: Refactoring](packets/A08-10.md) | A08-02 | done | [SPEC-001, CODE-001, CODE-005, TEST-001: pass; результат и handoff](experiments/A08-10/result.md) |
| [A08-11 — Подготовить S08b: Docs-only](packets/A08-11.md) | A08-02 | done | [SPEC-001, SPEC-006, PROC-003: pass; результат и handoff](experiments/A08-11/result.md) |
| [A08-12 — Подготовить S08c: Operational change](packets/A08-12.md) | A08-02 | done | [PROC-003, PROC-005: pass; результат и handoff](experiments/A08-12/result.md) |
| [A08-13 — Подготовить S09: Терминальные исходы](packets/A08-13.md) | A08-02 | done | [PROC-001, PROC-002, PROC-006: pass; результат и handoff](experiments/A08-13/result.md) |
| [A08-14 — Подготовить S10: Прерывание и повторная нарезка](packets/A08-14.md) | A08-02 | done | [PROC-002, PROC-003, PROC-005: pass; результат и handoff](experiments/A08-14/result.md) |
| [A08-15 — Подготовить S11: Два Change и удаление функции](packets/A08-15.md) | A08-02 | done | [SPEC-005, SPEC-007, TEST-005, PROC-002: pass; результат и handoff](experiments/A08-15/result.md) |
| [A08-16 — Подготовить S12: Неверное evidence и недоверенный вход](packets/A08-16.md) | A08-02 | done | [PROC-006, CODE-002, TEST-004, SPEC-001: pass; результат и handoff](experiments/A08-16/result.md) |

## A09

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A09-01 — Откалибровать локальную модель на S02/S03/S04](packets/A09-01.md) | A03-03, A03-04, A08-03..A08-16 | done | [partial; a/b/c closed; prompts frozen](experiments/A09-01/result.md) |
| [A09-01a — Калибровка ornith на S02](packets/A09-01a.md) | A09-01 | done | [partial; r3–r5 TASK-001 Green; F-008; F-009 → A12](experiments/A09-01/result.md) |
| [A09-01b — Калибровка ornith на S03](packets/A09-01b.md) | A09-01a | done | [pass; r1–r3 Red→Green, spec unchanged](experiments/A09-01/result.md) |
| [A09-01c — Калибровка ornith на S04](packets/A09-01c.md) | A09-01b | done | [pass; r1–r3 blocked-on-decision, no Specify](experiments/A09-01/result.md) |
| [A09-02 — Измерить локальное исполнение S01: Пустой продукт и новая capability](packets/A09-02.md) | A09-01 | done | [fail; Specify/Decompose; F-010](experiments/A09-02/result.md) |
| [A09-03 — Измерить локальное исполнение S05: Несколько capabilities и policy](packets/A09-03.md) | A09-01 | done | [fail; Specify/Decompose; F-010](experiments/A09-03/result.md) |
| [A09-04 — Измерить локальное исполнение S06: Длинный raw input](packets/A09-04.md) | A09-01 | done | [fail; false DEC / F-010](experiments/A09-04/result.md) |
| [A09-05 — Измерить локальное исполнение S07: Большой каталог и capability](packets/A09-05.md) | A09-01 | done | [fail; stop at Analyze](experiments/A09-05/result.md) |
| [A09-06 — Измерить локальное исполнение S08a: Refactoring](packets/A09-06.md) | A09-01 | done | [fail; spec unchanged; Decompose/Specify](experiments/A09-06/result.md) |
| [A09-07 — Измерить локальное исполнение S08b: Docs-only](packets/A09-07.md) | A09-01 | done | [fail; Specify docs extras; Decompose/Implement](experiments/A09-07/result.md) |
| [A09-08 — Измерить локальное исполнение S08c: Operational change](packets/A09-08.md) | A09-01 | done | [fail; ops unchanged; Specify/Decompose](experiments/A09-08/result.md) |
| [A09-09 — Измерить локальное исполнение S09: Терминальные исходы](packets/A09-09.md) | A09-01 | done | [fail; r1 duplicate; r2/r3 no terminal](experiments/A09-09/result.md) |
| [A09-10 — Измерить локальное исполнение S10: Прерывание и повторная нарезка](packets/A09-10.md) | A09-01 | done | [fail; Specify 3/3; interrupt not-run](experiments/A09-10/result.md) |
| [A09-11 — Измерить локальное исполнение S11: Два Change и удаление функции](packets/A09-11.md) | A09-01 | done | [fail; r1 Verify; r2/r3 Specify; F-006 not-run](experiments/A09-11/result.md) |
| [A09-12 — Измерить локальное исполнение S12: Неверное evidence и недоверенный вход](packets/A09-12.md) | A09-01 | done | [fail; Specify 3/3; authority intake pass; forged Green not-run](experiments/A09-12/result.md) |
| [A09-13 — Свести измерения локального профиля](packets/A09-13.md) | A09-01, A09-02, A09-03, A09-04, A09-05, A09-06, A09-07, A09-08, A09-09, A09-10, A09-11, A09-12 | done | [pass; holdout profile fail; local-results.md](experiments/A09-13/result.md) |

## A10

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A10-01 — Сравнить DeltaFuse с минимальным SDD](packets/A10-01.md) | A09-13 | done | [pass; SDD reaches S05 files, not quality; sdd-vs-deltafuse.md](experiments/A10-01/result.md) |
| [A10-02 — Проверить цену отдельных механизмов](packets/A10-02.md) | A10-01 | done | [pass; 1-slice extra OFF → 2 slices, F-010 remains; ablation.md](experiments/A10-02/result.md) |

## A11

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A11-01 — Сопоставить механизмы Spec Kit](packets/A11-01.md) | A02-10, A03-04, A03-05 | done | [pass; v1.0.4 chain not a DF replacement; comparison.md](experiments/A11-01/result.md) |
| [A11-02 — Сопоставить механизмы OpenSpec](packets/A11-02.md) | A02-10, A03-04, A03-05 | done | [pass; v1.12.0 delta-archive not a DF replacement; comparison.md](experiments/A11-02/result.md) |
| [A11-03 — Сопоставить механизмы BMAD Method](packets/A11-03.md) | A02-10, A03-04, A03-05 | done | [pass; v6.12.0 right-size not a gate skip; comparison.md](experiments/A11-03/result.md) |
| [A11-04 — Сопоставить механизмы Kiro Specs](packets/A11-04.md) | A02-10, A03-04, A03-05 | done | [pass; public docs EARS/req-design-tasks; Kiro not a DF replacement; comparison.md](experiments/A11-04/result.md) |
| [A11-05 — Проверить первичные практики по находкам](packets/A11-05.md) | A11-01, A11-02, A11-03, A11-04, A07-03 | done | [pass; ADR/BDD/EARS/mutation/repro/CM vs F-001..F-005; comparison.md](experiments/A11-05/result.md) |
| [A11-06 — Сравнить два аналога на S02/S04/S05](packets/A11-06.md) | A08-03, A08-04, A08-05, A08-06, A08-07, A08-08, A08-09, A08-10, A08-11, A08-12, A08-13, A08-14, A08-15, A08-16, A09-13, A11-05 | done | [pass; OpenSpec+Spec Kit contracts; live analog runs not-tested; comparison.md](experiments/A11-06/result.md) |

## A12

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A12-01 — Сверить покрытие и доказательность выводов](packets/A12-01.md) | A09-13, A10-02, A11-06 | done | [pass; coverage.md; A01-pass ≠ product; SUT gaps not-tested](experiments/A12-01/result.md) |
| [A12-02 — Ответить на четыре исходных вопроса](packets/A12-02.md) | A12-01 | done | [pass; four answers + core vs optional; summary.md](experiments/A12-02/result.md) |
| [A12-04 — Разобрать отложенные вопросы доработки](packets/A12-04.md) | A12-02 | done | [pass; Q-004 reject; Q-001/002/005/006/008 accept; parking](experiments/A12-04/result.md) |
| [A12-03 — Сформировать roadmap проверяемых изменений](packets/A12-03.md) | A12-02, A12-04 | done | [pass; RM-* P0–P3; roadmap.md; queue complete](experiments/A12-03/result.md) |

## A13

Регресс реализации RM-*. Не новый аудит. План: [regression-plan.md](regression-plan.md).

| Задача | Зависимости | Статус | Evidence / блокировка |
|---|---|---|---|
| [A13-01 — Контрактный регресс RM-* (без LLM)](packets/A13-01.md) | RM-031 на ветке | done | [pass; pytest 160+skip PBT; PS smoke; bash archive](experiments/A13-01/result.md) |
| [A13-02 — P0 holdout на ornith](packets/A13-02.md) | A13-01 | done | [partial; F-010 не vacuous; S02/S04 не дошли](experiments/A13-02/result.md) |
| [A13-03 — Маршруты docs/ops и Analyze на ornith](packets/A13-03.md) | A13-02 | done | [partial; route docs/ops; Specify YAML-fail; 1 slice](experiments/A13-03/result.md) |
| [A13-04 — Неизвестные A12 на SUT](packets/A13-04.md) | A13-02 | done | [partial; S11 Specify fail; F-006 not-run](experiments/A13-04/result.md) |
