# Результат эксперимента A11-05

- **ID карточки:** A11-05
- **Ревизия старта:** `ac484b2`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-003`, `TEST-001`, `TEST-002`, `PROC-002`, `PROC-004`, `CODE-006`
- **Вердикт:** **pass** — именованные практики сверены с находками A02–A07; у каждой рекомендации есть источник и условие отказа; нерелевантные практики исключены. LLM **не** вызывали.

## Гипотеза

ADR, BDD, RFC 2119 / EARS, contract/property/mutation testing, reproducible builds и change management закрывают находки A02–A07 лучше, чем текущие контракты DeltaFuse, и их стоит перенести пакетом.

**Альтернатива:** DF уже имеет `DEC-*`, RFC 2119, TASK GWT и протокол A07-03. Закрывают доказательства: EOL/hash (F-001), `converged` terminals (F-005), path canonicalization (F-004). Pact, Cucumber, PIT-как-зависимость и tokenizer-практики из списка **не** закрывают F-002/F-003.

Привязка: F-001…F-005, A07-03, SPEC-003, TEST-001/002, PROC-002, KI-02/KI-07 (не переранжировать Kiro).

## Ожидаемое

`sources.md` (URL, дата, раздел); `comparison.md` с решениями и условием отказа; нерелевантные практики с причиной исключения; `manifest.yaml`; этот `result.md`.

## Наблюдаемое

Таблица: [comparison.md](../../matrices/comparison.md) (секция Primary practices). Источники: [sources.md](sources.md).

| Решение | Строки |
|---|---|
| **сохранить** | PP-01 DEC; PP-02 TASK GWT; PP-03 RFC 2119; PP-05 протокол A07-03 (не PIT) |
| **адаптировать** | PP-07 `.gitattributes`/LF (F-001); PP-08 `cancelled`/`superseded` на `converged` (F-005); PP-09 `is_relative_to` (F-004) |
| **исследовать** | PP-04 EARS-стиль spec; PP-06 optional PBT (KI-07), не раннер Kiro |
| **не переносить** | PP-10 Pact |
| **исключено** | PP-X1 F-002; PP-X2 F-003 → Q-002 |

OWASP Path Traversal — один доп. источник плана на доказанный пробел F-004, не пятый SDD-аналог.

## Ограничения

Контракты и первичные docs, не runtime. Hypothesis docs fetch timeout — класс PBT всё равно зафиксирован (KI-07 + A07-03). NIST 800-128 — страница публикации, не полный PDF. IEEE EARS — DOI only. Tools не ставили. A09 findings не расширяли карточку.

## Handoff

- **Готово A11-05:** `done` / `pass`. Дальше [A11-06](../../packets/A11-06.md).
- A11-06: ни один из четырёх аналогов **не** first-class на llama-server `:1240` / ornith (A11-01…04). Живой прогон S02/S04/S05 при том же SUT **недоступен** → **not-tested**, только контракты; качество **не** ранжировать. Если позже появится сопоставимый harness: OpenSpec (change/archive) и Spec Kit `generic` / BMAD right-size; Kiro **not-applicable**.
- A12: фиксы F-001 / F-004 / F-005; EARS-стиль и optional PBT как исследование, не вендор. Skills не патчить.
- Новых Q в parking нет (F-003 уже Q-002; F-002 — код FSM, не практика из списка).
