# Бенчмарк воркера (агент-агностичный)

[**English**](bench.md) | [Русский](bench.ru.md)

Счёт идёт **по файлам на диске**. Ядро модель не вызывает.

Песочница воркера и хост судьи разделены. Воркер не видит пак с оракулом. Судья не пишет scorecard в песочницу.

## Изоляция

| | Песочница воркера | Хост судьи |
|---|---|---|
| Workspace | Только каталог после `bench init` | Checkout фреймворка или `--pack` |
| Команды | `next`, `check-gate`, `evidence`, … | `bench score --pack …`, `bench compare`, `bench journal` |
| Видит | Intake, seed spec/code, skills | `oracle.yaml`, `hidden_suite`, журнал ядра |
| Нельзя | `bench score`, поиск в parent repo, самоотчёт retries | `--out-file` внутри песочницы |

Агент открывает **каталог продукта**, не `delta-fuse`. `DELTAFUSE_BENCH_PACK` — только у судьи.

## Команды

```text
deltafuse bench init M02-policy-stats C:\work\m02-opus
deltafuse bench journal C:\work\m02-opus
deltafuse bench score C:\work\m02-opus --pack C:\src\delta-fuse --json --label cursor+opus-5 --out-file C:\scores\opus.json
deltafuse bench compare C:\scores\opus.json C:\scores\flash.json
```

Если каталог уже есть, init отказывается и печатает команду пересоздания. `deltafuse bench init … --force` (или `-f`) стирает его и ставит чистую песочницу.

Цифры (`schema_version` 3):

- **score** — рейтинг. `0.6 * correctness + 0.4 * process`, если есть журнал retries. **Без журнала — `n/a`.** Не публиковать `correctness=100` как сравнение воркеров.
- **correctness** — взвешенные баллы оракула. Presence и `already past this gate` не считаются. Hidden-тесты разделены (lockout > isolation > backward compat).
- **process** — доля успешных `check-gate` по журналу `.deltafuse/bench-journal.jsonl` (старый YAML ещё читается). Нет журнала — `n/a`, не ноль.
- **efficiency** — `correctness * process / 100`.
- **retries** — провалы `check-gate` + `evidence` + `coverage`.

Ядро в песочнице пишет одну JSON-строку на каждую CLI-команду (`next`, `check-gate`, `evidence`, …). У `check-gate` — `ok`, `gate`, `errors`. Собрать попытки: `deltafuse bench journal <product-dir>` (циклы: подряд один гейт до успеха). Человек, чужой агент и свой агент одинаковы: журнал им писать не поручают.

`M01-cooldown` — **пол**. Фронтир — `M02-policy-stats`: два capability, два live spec, публичный API (`peak_rate`, `token_rejects`, `reject_threshold`, `block_seconds`, `stats.py` / `policy.py`) задан во intake как `penalty_seconds` на M01. Hidden: раздельные счётчики, окно 1s, lockout только по consecutive, без debit в блоке, без Redis. Сравнивать по `score` (нужен журнал) или по M02. Бинарный `pass` / `first_fail` остаётся закрытием прогона.

Mock `deltafuse eval` (one-shot dump пакета) удалён в 2.4.0. Скоринг воркера — этот bench.
