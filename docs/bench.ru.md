# Бенчмарк воркера (агент-агностичный)

[**English**](bench.md) | [Русский](bench.ru.md)

Счёт идёт **по файлам на диске**. Ядро модель не вызывает.

Песочница воркера и хост судьи разделены. Воркер не видит пак с оракулом. Судья не пишет scorecard в песочницу.

## Изоляция

| | Песочница воркера | Хост судьи |
|---|---|---|
| Workspace | Только каталог после `bench init` | Checkout фреймворка или `--pack` |
| Команды | `next`, `check-gate`, `evidence` | `bench score --pack …`, `bench compare` |
| Видит | Intake, seed spec/code, skills | `oracle.yaml`, `hidden_suite` |
| Нельзя | `bench score`, поиск в parent repo | `--out-file` внутри песочницы |

Агент открывает **каталог продукта**, не `delta-fuse`. `DELTAFUSE_BENCH_PACK` — только у судьи.

## Команды

```text
deltafuse bench init M01-cooldown C:\work\m01-opus
deltafuse bench score C:\work\m01-opus --pack C:\src\delta-fuse --json --label cursor+opus-5 --out-file C:\scores\opus.json
deltafuse bench compare C:\scores\opus.json C:\scores\flash.json
```

`--verbose` добавляет вывод hidden pytest — воркеру его не показывать. Главная метрика: 7 бит шагов + `first_fail`, не одно число 0.73.
