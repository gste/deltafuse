# Контракт halt (DeltaFuse ↔ хост)

[English](halt.md) | [**Русский**](halt.ru.md)

Машинная схема: [halt.schema.yaml](halt.schema.yaml) (контракт v1).

**Канон продюсера** — этот репозиторий. Хост (Cursor, IDE, оркестратор) пинит ту же схему. Это не схема продукта; installer не копирует `docs/contracts/**` в продукт.

Продюсер: `deltafuse next --json` (`deltafuse.core.queue.build_halt`). Клик: `deltafuse decide`. Ядро не рисует кнопки, не auto-accept и не делает `git push`.

`halt` — объект по этой схеме или JSON `null`. `null` — готов шаг воркера: выполнить skill, кнопок нет.

## Роли

| Сторона | Где | Обязанность |
|---|---|---|
| Продюсер | Ядро DeltaFuse | Отдать валидный `halt`. Нет merge/`git push`. |
| Потребитель | Хост | Показать `choices` кнопками. Ждать. Выполнить только `choice.command`. Воркер не выбирает. |
| Воркер | LLM или человек | Пишет файлы Change. На Human Gate останавливается. |
| Склад | git продукта | Decisions, spec, Change. `decide` пишет клик. |

## Хост обязан

Кнопки — только `halt.choices[].label`. Ненулевой `command` — запустить как есть из корня продукта (`deltafuse decide …`). `id: inspect` / `command: null` — стоп, не `decide`. Ждать человека. Пак бенча (`oracle.yaml`, `hidden_suite`) не класть в песочницу воркера и не в адаптеры skills. Доска — другой репозиторий, читает [снимок](board-snapshot.ru.md).

## Транспорт

```text
deltafuse next <product-root> --json
deltafuse decide <change-dir> --decision DEC-0001 --status accepted
deltafuse decide <change-dir> --spec --status accepted
```

Stdout при `--json` — один JSON. `next` не пишет продукт. `decide` — единственная запись клика Human Gate. `check-gate` отвергает `accepted`/`rejected` без записи в `.deltafuse/gate-journal.jsonl`.

## Запреты

Хост: не давать воркеру выбрать choice; не auto-accept DEC/spec/merge/push; не добавлять кнопки merge/push; не копировать pack в sandbox; не рисовать fuse-map из `docs/changes/**`. Продюсер: не отдавать command кроме `deltafuse decide …` / `null`; не auto-accept; не класть oracle в JSON; не рисовать UI в `src/deltafuse/**`.

Пример JSON — в [английской версии](halt.md).
