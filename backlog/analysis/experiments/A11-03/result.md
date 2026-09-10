# Результат эксперимента A11-03

- **ID карточки:** A11-03
- **Ревизия старта:** `9248091`
- **Статус исполнения:** **done**
- **Критерии:** `PROC-001`, `PROC-004`, `PROC-006`, `SPEC-002`
- **Вердикт:** **pass** — BMAD v6.12.0 + docs 2026-09-08 зафиксированы; матрица дополнена. Качество vs ornith **not-tested**.

## Гипотеза

Контракты ролей, передача контекста и выбор глубины workflow по размеру работы в BMAD лучше масштабируют процесс, чем один lifecycle DeltaFuse, и их стоит перенести.

**Альтернатива:** DF уже режет работу фазами FSM и `context_budget`; «skip Specify / self-review / unattended build» конфликтует с Human Gate и независимым oracle. Практика sizing полезна как **профиль lock** (Q-001), не как каталог агентов.

Привязка: Q-001, AB-06, A03-04/05, `docs/roles.md`.

## Ожидаемое

`sources.md` с URL/release/commit/датой/разделом; строки в `matrices/comparison.md`. Один механизм. Популярность не proof. Пакетный `analysis/matrices/contracts.md` отсутствует.

## Наблюдаемое

Таблица: [comparison.md](../../matrices/comparison.md) (секция BMAD). Источники: [sources.md](sources.md).

Pin: **v6.12.0** published 2026-09-04, commit `05bfbd46d00766ec88eb9b42e76be2c575d64d7b`. Docs site 2026-09-08 (может опережать тег; `main` = `abe4eb1b`). Код MIT (BMad Code, LLC); товарные знаки **не** под MIT. GitHub SPDX `NOASSERTION`.

Решения: **не переносить** skip-gates, `bmad-build-auto`, self-review как Verify, мультиагентные «perspectives» как отдельные модели; **сохранить** FSM + Maintainer; **исследовать** right-size как lock-профиль (Q-001) и короткий AGENTS-блок (Q-007).

Инструменты: Claude Code / Cursor на landing; llama-server/ornith **не** в docs. `--list-tools` не запускали. Installer не ставили.

## Ограничения

Контракты, не runtime. Docs ≠ commit тега. Skills в `_bmad` не читались. Trademark ограничивает копирование имён, не только кода.

## Handoff

- **Готово A11-03:** `done` / `pass`. Дальше [A11-04](../../packets/A11-04.md) (Kiro Specs).
- A11-06: BMAD **not-tested** на `:1240`. Не ранжировать vs Claude/Cursor.
- A12: Q-001 (ceremony после расследования ≠ снятие гейта); Q-007; не брендировать DF как BMad.
- Skills / integrity не патчить.
