# Результат эксперимента A11-01

- **ID карточки:** A11-01
- **Ревизия старта:** `6c08de9`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-002`, `PROC-001`, `PROC-006`
- **Вердикт:** **pass** — первичные источники Spec Kit v1.0.4 зафиксированы; матрица решений заполнена. Качество vs ornith **not-tested**.

## Гипотеза

Цепочка Spec Kit (constitution / spec / plan / tasks / implement / converge) решает те же проблемы, что Change FSM DeltaFuse, и её стоит перенести целиком.

**Альтернатива:** это markdown-SDD без независимых гейтов; польза для DF ограничена адаптацией процесса (конституция/профили), а не заменой ядра. A10-01 уже показал, что «просто SDD» не улучшение.

Привязка: ANA-01/02, SPC-01/06, F-010, AB-06, Q-001.

## Ожидаемое

`sources.md` с URL/release/commit/датой/разделом; `matrices/comparison.md` со строками проблема→механизм→evidence→эквивалент→выгода/цена/риск/решение и лицензией. Один механизм. Популярность не proof.

Пакетный `analysis/matrices/contracts.md` отсутствует — контракты из `backlog/matrices/contracts.md`.

## Наблюдаемое

Таблица: [comparison.md](../../matrices/comparison.md) (секция Spec Kit). Источники: [sources.md](sources.md).

Pin: **v1.0.4** published 2026-09-02, commit `cb610277fdea781fcfa83d20522c2db37c94068d`. `main` на сверке `4a7341a93d944d6efe153b71da4a1adb9c2b578c` (2026-09-04). MIT, GitHub, Inc.

Решения: **не переносить** slash-SDD и converge-без-oracle; **сохранить** typed tasks, hidden Verify, human DEC gate, FSM `specified`; **исследовать** constitution-как-lock (Q-007) и усиление `specified` (F-010); catalog extensions **не переносить**.

Интеграции: Cursor/`generic` есть; llama-server/ornith **нет** в таблице. Установку Spec Kit не делали.

## Ограничения

Контракты, не runtime. Docs site ≠ commit тега. `generic --commands-dir` не проверяли. Шаблоны не читались целиком (copyright: summary + cite).

## Handoff

- **Готово A11-01:** `done` / `pass` (полнота сопоставления). Дальше [A11-02](../../packets/A11-02.md) (OpenSpec).
- A11-05/A11-06: Spec Kit кандидат только если появится тот же SUT; иначе контракты. Не ранжировать ornith vs Copilot.
- A12: F-010; Q-001/Q-007; не копировать Spec Kit templates без MIT notice.
- Skills / integrity не патчить.
