# Результат эксперимента A11-04

- **ID карточки:** A11-04
- **Ревизия старта:** `8c71633`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-003`, `SPEC-004`, `DEC-02`, `TEST-001`
- **Вердикт:** **pass** — публичные Kiro Specs docs зафиксированы; матрица дополнена. Runtime и ornith **not-tested**.

## Гипотеза

Связка requirements.md → design.md → tasks.md и EARS дают проверяемые требования лучше, чем spec-delta + TASK oracle DeltaFuse, и их стоит перенести.

**Альтернатива:** DF уже имеет spec → DEC → TASK с оракулом и RFC 2119 (SPEC-003). Полезны формулировка WHEN/SHALL и явный unchanged-behavior для багов; три markdown-файла без schema и Quick Spec без гейтов — нет.

Привязка: SPC-01, DEC-02/03, SPEC-003/004, F-010.

## Ожидаемое

`sources.md` с URL, датой docs, пределом версии (нет git pin); `comparison.md` со строками и лицензией. Один механизм. Популярность не proof. Управляемый продукт: internals **not-tested**.

## Наблюдаемое

Таблица: [comparison.md](../../matrices/comparison.md) (секция Kiro). Источники: [sources.md](sources.md).

Pin: docs `kiro.dev/docs/specs/` updated 2026-08-27; Analyze Requirements 2026-09-02. Open-source commit **нет**. Продукт proprietary.

Решения: **сохранить** spec-delta + typed TASK + RFC 2119; **исследовать** EARS-стиль в `docs/spec/**` (SPEC-003/004) и PBT как опциональный oracle, не Kiro-генератор; **не переносить** Quick Spec, Design-First как Specify, `#spec` полный комплект в каждый чат, parallel waves на ornith.

## Ограничения

Нет LICENSE/SPDX. Docs copyright. PBT и волны — только заявлены в docs, код не инспектировали. Claude/Kiro IDE ≠ `:1240`.

## Handoff

- **Готово A11-04:** `done` / `pass`. Дальше [A11-05](../../packets/A11-05.md) (первичные практики по находкам).
- A11-06: Kiro **not-tested** / **not-applicable** на llama-server. Кандидаты живого сравнения — только аналоги с открытым CLI при том же SUT.
- A12: EARS как стиль spec (не файлы `.kiro`); Analyze Requirements не заменяет F-010 live paths; PBT — практика, не продукт.
- Skills не патчить. Шаблоны Kiro не копировать.
