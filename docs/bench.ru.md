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
deltafuse bench init M02-policy-stats C:\work\m02-opus
deltafuse bench score C:\work\m02-opus --pack C:\src\delta-fuse --json --label cursor+opus-5 --out-file C:\scores\opus.json
deltafuse bench compare C:\scores\opus.json C:\scores\flash.json
```

Цифры (`schema_version` 3):

- **score** — рейтинг. `0.6 * correctness + 0.4 * process`, если есть журнал retries. **Без журнала — `n/a`.** Не публиковать `correctness=100` как сравнение воркеров.
- **correctness** — взвешенные баллы оракула. Presence и `already past this gate` не считаются. Hidden-тесты разделены (lockout > isolation > backward compat).
- **process** — доля успешных `check-gate` по журналу `.deltafuse/bench-journal.yaml`. Нет журнала — `n/a`, не ноль.
- **efficiency** — `correctness * process / 100`.
- **retries** — провалы `check-gate` + `evidence` + `coverage`.

`M01-cooldown` — **пол**. Фронтир — `M02-policy-stats`: два capability (usage stats + consecutive policy), два live spec, hidden на раздельные счётчики reject / окно peak_rate / lockout только по consecutive / без debit в блоке / без Redis. Сравнивать по `score` (нужен журнал) или по M02. Бинарный `pass` / `first_fail` остаётся закрытием прогона.
