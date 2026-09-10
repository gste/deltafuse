# A02-03 — Проверить контракт Route and Analyze

**Verdict: `pass` для условий карточки.** На ревизии `60ea40438b0142797848356c660ab88286565e7d` (рабочий HEAD `9099b407a5180f17bca8586071a17950c4fe30c0`) выполнена детальная сверка контракта второй фазы жизненного цикла — **Route and Analyze** — по сквозной цепочке «инвариант → документация → навык агента → схема/шаблон → runtime gate FSM → юнит/мутационный тест».

Результаты сопоставления зафиксированы в разделе 5 матрицы [backlog/matrices/contracts.md](../../../matrices/contracts.md).

## Подтверждённые инварианты фазы Route and Analyze

1. **ANA-01 (Двунаправленное покрытие claims):** Функция `validate_coverage_completeness` в `integrity.py` строго сверяет все `CR-*` из `request.md` с маппингом в `coverage.yaml`. Потеря хотя бы одного claim или появление orphan claim приводит к немедленному падению гейта.
2. **ANA-02 (Блокировка на нерешённых решениях человека, Human Gate):** Функция `find_unresolved_decisions_for_change` в `integrity.py` и проверка в гейте `analyzed` гарантируют, что если для Change существует хотя бы одна архитектурная запись `DEC-*` в статусе `proposed`, Change переходит в статус `blocked-on-decision`. Переход в `analyzed` или `specified` физически блокируется до тех пор, пока человек не изменит статус на `accepted` или `rejected`.
3. **ANA-03 (Обязательность слайсов и дельт):** Гейт `analyzed` требует наличия непустого каталога `slices/*.md`, валидации каждого слайса схемой `slice.schema.yaml` и структуры типизированных дельт по 7 нормативным проекциям.
4. **ANA-04 (Бюджет контекста среза):** Для каждого файла среза `slices/*.md` FSM валидирует контекстный бюджет `context_budget` по файлам спецификаций из `spec_refs`.
5. **ANA-05 (Таблица допустимых переходов):** Из `analyzing` строго разрешены переходы в `blocked-on-decision`, `analyzed`, `rejected`, `duplicate`, `superseded`, `not-reproduced`. Из `analyzed` — в `specification-proposed`, `specified`, `targeting`.

## Наблюдения и ограничения

- **Семантика Red/Green:** В фазе Route and Analyze тесты Target ещё не написаны, Red и Green доказательные состояния не фигурируют; объём изменений по тестам и коду декларируется проекциями дельт (`tests.operation`, `implementation.operation`).
- **Разрыв контроля каталога (ANA-06):** Схема `routing.schema.yaml` требует строковое поле `primary_capability`, но FSM не сверяет его с реальным каталогом `docs/spec/_capabilities.yaml`. При наличии опечатки в имени capability гейт `analyzed` проходит успешно (разрыв будет адресован в рекомендациях A12).

## Handoff

- **Фаза Route and Analyze верифицирована:** инварианты ANA-01..ANA-06 подтверждены и занесены в [backlog/matrices/contracts.md](../../../matrices/contracts.md).
- **Следующая задача по очереди:** [A02-04 — Проверить контракт Specify](../../packets/A02-04.md) (исследование применения дельт к нормативной спецификации `docs/spec/**` и Human Gate спецификации).
