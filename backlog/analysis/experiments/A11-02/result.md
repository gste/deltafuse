# Результат эксперимента A11-02

- **ID карточки:** A11-02
- **Ревизия старта:** `647df37`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-007`, `PROC-001`, `PROC-006`
- **Вердикт:** **pass** — OpenSpec v1.12.0 зафиксирован; матрица решений дополнена. Качество vs ornith **not-tested**.

## Гипотеза

Change-папка OpenSpec + слияние delta в основную spec на archive лучше решает brownfield и актуальность spec (SPEC-007), чем Change FSM DeltaFuse, и её стоит перенести.

**Альтернатива:** DF уже имеет spec-delta + архив пакета; OpenSpec откладывает SSOT до после кода и снимает гейты — это конфликт с «spec — закон до реализации» и с AB-06.

Привязка: SPC-01/04/05, VER-05/06, F-010, SPEC-007.

## Ожидаемое

`sources.md` с URL/release/commit/датой/разделом; строки в `matrices/comparison.md`. Один механизм. Популярность не proof. Пакетный `analysis/matrices/contracts.md` отсутствует.

## Наблюдаемое

Таблица: [comparison.md](../../matrices/comparison.md) (секция OpenSpec). Источники: [sources.md](sources.md).

Pin: **v1.12.0** published 2026-09-03, commit `e062b9572be933564ba3899d059377dfa1393e32` (= `main` на сверке). MIT, OpenSpec Contributors.

Решения: **не переносить** fluid-без-гейтов и merge SSOT только на archive; **сохранить** Specify-time `docs/spec/**`, typed spec-delta, archiver T8, SPC-05 на Specify; **исследовать** delta-first bootstrap (F-010) и Q-008 (проверка merge после Verify, не замена Specify).

Инструменты: Cursor/`.agents` есть; llama-server/ornith **нет**. README рекомендует Codex 5.5 / Opus 4.7 — несопоставимо с ornith. CLI не ставили.

## Ограничения

Контракты, не runtime. `concepts.md` timeout. `/opsx:sync` и expanded `/opsx:verify` не ставились. Шаблоны не копировались.

## Handoff

- **Готово A11-02:** `done` / `pass`. Дальше [A11-03](../../packets/A11-03.md) (BMAD).
- A11-06: OpenSpec **not-tested** на `:1240`, пока нет того же SUT. Не ранжировать vs Opus.
- A12: F-010 bootstrap; Q-008; SPEC-007 уже покрыт операциями spec-delta — не копировать markdown ADDED-секции.
- Skills / integrity не патчить.
