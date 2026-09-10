# Бенчмарк воркера (агент-агностичный)

[**English**](bench.md) | [Русский](bench.ru.md)

Счёт идёт **по файлам на диске**. Ядро модель не вызывает. Cursor, Claude, Gemini, человек и будущий свой агент заполняют одно и то же дерево продукта.

## Кейс

`M01-cooldown` — добавить `penalty_seconds` к существующему limiter `security.ratelimit`. Одна capability, полный lifecycle. Hidden suite в продукт не копируется.

Оракул и `hidden_suite` живут в `process/bench/cases/M01-cooldown/`.

## Команды

```text
deltafuse bench init M01-cooldown C:\work\m01-opus
deltafuse bench score C:\work\m01-opus --json --label opus-5 --out-file opus.json
deltafuse bench compare opus.json flash.json
```

`--stage specify` — один шаг. Exit `0` только если все запрошенные шаги pass.

Не копировать hidden-тесты в `tests/` продукта. Human Gate не auto-accept. Это не `deltafuse eval --provider mock` и не харнесс A09.
