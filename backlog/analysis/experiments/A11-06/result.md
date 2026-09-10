# Результат эксперимента A11-06

- **ID карточки:** A11-06
- **Ревизия старта:** `439c54e`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-002`, `PROC-004`, `PROC-007`, `TEST-001`
- **Вердикт:** **pass** (полнота: два кандидата, контракты на S02/S04/S05, отказ от ранга). Живой прогон аналогов на том же SUT — **not-tested**. Качество vs ornith **не** ранжировано.

## Гипотеза

Два наиболее релевантных аналога на S02/S04/S05 при сопоставимых ресурсах покажут, какой процесс лучше DeltaFuse на ornith.

**Альтернатива:** ни один из четырёх аналогов не имеет first-class интеграции с llama-server `:1240`. Живой прогон был бы либо чужой моделью (несопоставимо), либо новым харнессом (это A10-01, не продукт аналога). План A11 тогда требует контракты без ранга качества.

Привязка: protocol §1/§4; SK-08, OS-07, BM-07, KI-09; A09-13; A10-01.

## Ожидаемое

Два аналога на S02, S04, S05, один case за запуск, те же модель/oracles/бюджеты. Если интеграции нет — только контракты; не ранжировать.

## Наблюдаемое

SUT `:1240` / `ornith-1.5-35b-a3b` **доступен** (`GET /v1/models`, 2026-09-08). Интеграции аналогов — нет.

Два кандидата: **OpenSpec** (change/archive ≈ DF CHG-*) и **Spec Kit** (`generic --commands-dir`). BMAD не выбран (IDE installer). Kiro **not-applicable**.

Таблица: [comparison.md](../../matrices/comparison.md) (секция A11-06). Источники: [sources.md](sources.md).

Контрактно, без ранга:

| Case | DF (измерено) | Spec Kit | OpenSpec |
|---|---|---|---|
| S02 tiny (calibration) | A09 `partial`: TASK Green, 0 Verify, F-009 | slash specify→tasks→implement; нет typed TASK / hidden (SK-03/04) | propose/apply/archive; fluid, не гейт (OS-01/05) |
| S04 Decision (calibration) | A09 `pass`: `blocked-on-decision` + DEC | `/speckit.clarify` рекомендован, не блок (SK-05) | «no rigid phase gates» (OS-05) |
| S05 multi-cap (holdout) | A09 `fail` Specify/F-010; A10-01 SDD файлы, pytest не green | converge = self-review (SK-04); S05 нельзя тюнить под аналог (§1) | несколько delta spec, merge на archive (OS-03) |

Не ставить analog выше/ниже DF по качеству. A10-01 уже показал: дешёвый SDD на том же SUT не замена ядра.

## Ограничения

CLI аналогов не ставили. `generic` / `.agents` не гоняли. n живых analog-прогонов = 0. Protocol.md не содержит заголовка «сопоставимость».

## Handoff

- **Готово A11-06:** `done` / `pass` (контрактный fallback). Analog quality vs ornith **not-tested**. Дальше [A12-01](../../packets/A12-01.md).
- A12: не объявлять Spec Kit/OpenSpec/BMAD/Kiro лучше DF на S02/S04/S05. Заимствования — только строки A11-01…05 с условием отказа. Не копировать шаблоны.
- Повторный живой ранг — только если появится first-class адаптер того же `:1240` / той же модели / тех же oracles. Обёртка CLI ≠ интеграция продукта.
- Skills не патчить.
