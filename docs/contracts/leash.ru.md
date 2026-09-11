# Конверт записи (DeltaFuse ↔ leash / хост)

[English](leash.md) | [**Русский**](leash.ru.md)

Машинная схема: [leash.schema.yaml](leash.schema.yaml) (контракт v1).

**Канон продюсера.** `deltafuse leash`, hook или хост пинят ту же схему. Не схема продукта; installer не копирует `docs/contracts/**`.

Продюсер: `deltafuse next --json`. Проверка: `deltafuse leash`. `envelope` — объект по схеме или JSON `null`. `null` — нет готового шага воркера. Пути продукта (`src/**`, `tests/**`, `docs/spec/**`) в таком diff — orphan, `leash` падает. `docs/intake/**` и `AGENTS.md` не orphan.

Intake `write` не содержит `src/**`. Declare/Implement оставляют evidence и `tests/**`, код сужается до `allowed_paths`. `workflow.leash: advisory` — те же нарушения, exit 0.
