# Результат эксперимента A08-15

- **ID карточки:** A08-15
- **Ревизия:** `ca3cd73`
- **Критерии:** `SPEC-005`, `SPEC-007`, `TEST-005`, `PROC-002`
- **Вердикт:** **pass** (сценарий S11: два Change и удаление функции подготовлен в holdout-сплите с оракулом инвалидации evidence и актуальности spec)

## Ожидаемое поведение

1. **Характер сценария S11 (Concurrent Changes / Deletion / Holdout)**: CHG-A (burst_allowance) и CHG-B (window stats, `input.md`) стартуют с одной ревизии. После архивации CHG-A и merge в CHG-B устаревший Green не должен закрывать `converged`. Затем CHG-C удаляет burst: spec, код, тесты и каталог без остатков и битых якорей.
2. **Оракулы**: отказ stale Green; обязательная инвалидация или повторный прогон evidence; merged spec держит оба живых claim; после удаления нет `burst_allowance` и dangling refs.
3. **Мутации**: silent pass F-006, отсутствие инвалидации, потеря peer-claim, остаток burst, битые ссылки.

## Наблюдаемое поведение

1. Артефакты созданы в [cases/S11/](../cases/S11/).
2. Сценарий включен в holdout-выборку для A09-11.
3. Базовый размер лестницы: 2 Change, 1 общий spec-файл. Рост 2→4→8 пересекающихся claims — в A09-11, по образцу S06/S07.

## Ограничения

- Исполняющая модель CHG-B видит только `input.md`. Тексты CHG-A/CHG-C и merge-протокол — в `manifest.yaml` для харнесса.
- Oracle ожидает отказ stale Green. При неисправленном [F-006](../../../findings/F-006.md) прогон A09-11 должен дать `fail` по `test_stale_evidence_rejected_after_merge`.

## Handoff

- **Результат:** S11 подготовлен; критерии `SPEC-005`, `SPEC-007`, `TEST-005`, `PROC-002`; связанный дефект F-006.
- **Evidence:** [cases/S11/](../cases/S11/), [manifest](manifest.yaml).
- **Нерешённое:** фактические concurrent/deletion прогоны и геометрическая лестница — A09-11.
- **Далее:** [A08-16](../../packets/A08-16.md) — S12: неверное evidence и недоверенный вход.
