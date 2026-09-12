# Backlog

Очередь работ вокруг канонического репозитория DeltaFuse. Это не lifecycle продукта и не замена `docs/**`.

Брать в работу: [AU-001](product/AU-001.md) — полный внешний аудит. Промпт: [product/audit-prompt.md](product/audit-prompt.md).

Закрытая программа: [product/leash.md](product/leash.md).

| ID | Статус | Слой |
|---|---|---|
| [AU-001](product/AU-001.md) | `ready` | полный аудит (промпт → другие модели) |
| [LS-001](product/LS-001.md) | `done` | `next --json` write envelope |
| [LS-002](product/LS-002.md) | `done` | `deltafuse leash` |
| [LS-003](product/LS-003.md) | `done` | orphan-diff без Change |
| [LS-004](product/LS-004.md) | `done` | hook/CI + `workflow.leash` |
| [LS-005](product/LS-005.md) | `done` | Gate только через `decide` |
| [LS-006](product/LS-006.md) | `done` | штамп `deltafuse evidence` |
| [LS-007](product/LS-007.md) | `done` | контракт хоста (writes + halt) |

Сводка: [product/index.md](product/index.md).

Сделано ранее: [SK-001](product/SK-001.md), [HS-001](product/HS-001.md).

Закрытые карточки, пакеты анализа, findings, матрицы и снимки экспериментов остаются в git history.

Последний коммит с полным деревом экспериментов: `e3e1149`.

```text
git log -- backlog/
git show e3e1149:backlog/analysis/experiments/A09-01/result.md
```

Не восстанавливать `backlog/analysis/experiments/**/work/**` в рабочее дерево: Cursor индексирует вложенные `AGENTS.md` и `.cursor/skills/**` как скиллы воркспейса.


# After Audit #2

Ниже полный список обнаруженных дефектов. Их лучше оформить как отдельную программу стабилизации перед объявлением v3.0.0.

## Блокеры релиза

### V3-FIX-001 — Qualification runner не выполняет прогоны

`scripts/qualify.py` только проверяет доступность LM Studio. `run_case()` всегда завершает работу через `SystemExit`.

Последствия:

- ни один M01/M02/M03 реально не запускается;
- thresholds не применяются;
- медианы не рассчитываются;
- manifests и per-run reports не создаются.

Доработка:

- реализовать создание чистой песочницы;
- вызвать Worker через LM Studio;
- проверить точный model ID и context limit;
- собрать журнал, score и context metrics;
- применить T1–T8;
- сохранить каждый run отдельно;
- рассчитать медианы без сокрытия неудачных запусков.

### V3-FIX-002 — Обязательные qualification runs отсутствуют

Не выполнены три запуска для каждого из M01, M02 и M03. В [`release-report.md`](product/v3/release-report.md) все результаты имеют статус `_pending_`.

Доработка:

- после исправления runner выполнить девять чистых запусков;
- опубликовать model/framework provenance;
- сохранить все результаты, включая неуспешные;
- закрывать DF3-009 только если каждый запуск проходит абсолютные пороги.

### V3-FIX-003 — Версия фреймворка остаётся 2.5.0

`VERSION`, Python package и `pyproject.toml` объявляют `2.5.0`. Оба smoke-теста устанавливают DeltaFuse 2.5.0.

Одновременно шаблон продукта содержит `framework.version: 3.5.0`, что тоже неверно.

Доработка:

- определить единый номер `3.0.0`;
- синхронизировать `VERSION`, `pyproject.toml`, `__version__`, templates, installer, bundle и документацию;
- добавить тест, проверяющий совпадение версии во всех источниках.

## M03 и benchmark

### V3-FIX-004 — M03 не содержит полноценного benchmark case

В каталоге M03 отсутствуют:

- `input.md`;
- `seed/**`;
- `hidden_suite/test_acceptance.py`.

`bench init M03-adversarial` создаёт песочницу без входной задачи и исходного продукта.

Доработка:

- создать самостоятельный seed-проект;
- добавить intake с нормальными продуктовым требованиями;
- реализовать независимый hidden suite;
- проверить M03 end-to-end через `bench init`, Worker, `bench score`.

### V3-FIX-005 — M03 case и oracle описывают разные задачи

[`case.yaml`](../process/bench/cases/M03-adversarial/case.yaml) ожидает `monitoring.usage_stats`, а [`oracle.yaml`](../process/bench/cases/M03-adversarial/oracle.yaml) проверяет `security.ratelimit` и `penalty_seconds`.

Фактически oracle скопирован из M01.

Доработка:

- выбрать одну продуктовую задачу M03;
- согласовать capability, claims, live spec, public API, seed и hidden tests;
- добавить schema/consistency test для пары `case.yaml` + `oracle.yaml`.

### V3-FIX-006 — Adversarial defense checks не подключены к scorer

`defense_checks` объявлены в `case.yaml`, но код их не читает.

Не проверяются:

- journal forgery;
- envelope escape;
- synthetic evidence;
- gate spam;
- oracle leak.

Доработка:

- реализовать обработчик каждого defense check;
- выводить отдельный результат по каждому в scorecard;
- считать любой такой дефект hard failure;
- добавить негативный тест на каждый вектор атаки.

### V3-FIX-007 — M03 теряет повышенный вес Process

В `case.yaml` задано `correctness: 0.4 / process: 0.6`, но oracle задаёт `0.6 / 0.4`. При загрузке oracle перезаписывает значение case через `data.update()`.

Доработка:

- оставить `score_mix` только в одном источнике;
- запрещать конфликтующие поля case/oracle;
- добавить тест, что M03 получает именно повышенный вес Process.

### V3-FIX-008 — Leak detection по-прежнему ограничен `tests/**`

Scorer ищет hidden-test markers только в Python-файлах каталога `tests`. Утечку можно разместить в:

- `src/**`;
- fixtures;
- документации;
- scripts;
- других расширениях файлов.

Таким образом, finding C-04 не закрыт.

Доработка:

- сканировать всё доступное Worker дерево;
- исключить служебные каталоги только по явному allowlist;
- сравнивать с полным набором секретных needles/hashes;
- добавить тесты утечки через `src`, fixture и непитоновский файл.

## Core-owned transitions

### V3-FIX-009 — Ручной статус принимается, если receipts ещё нет

`receipt_mismatch()` возвращает `None`, когда журнал переходов пуст. Поэтому Worker может вручную поставить продвинутый статус до первого Core receipt.

Например, Change с вручную выставленным `analyzed` и подходящими файлами может продолжить Process без зарегистрированного перехода.

Доработка:

- разрешать отсутствие receipt только для начального состояния;
- для любого продвинутого состояния требовать полную цепочку receipts;
- проверять цепочку в `next`, `check-gate`, `advance` и `archive`;
- добавить тесты ручного перехода в каждое состояние.

### V3-FIX-010 — Worker skills продолжают менять lifecycle state

Несмотря на правило «state пишет только Core», skills instruct Worker:

- выставить Change/task в `declared`;
- выставить task в `implemented`;
- поставить `specification-proposed`;
- менять статусы slices.

Особенно явно это записано в [`declare/SKILL.md`](../process/skills/declare/SKILL.md).

Доработка:

- удалить из Worker skills любые инструкции ручного изменения state;
- после успешного gate всегда вызывать `deltafuse advance`;
- определить Core-команды для slice/task state;
- синхронизировать generated bundle;
- добавить статический тест, запрещающий такие инструкции в skills.

### V3-FIX-011 — Single-step skills не вызывают `advance`

`run/SKILL.md` знает про `deltafuse advance`, но отдельные `intake`, `analyze`, `declare`, `implement` после `check-gate` сразу вызывают `next`.

Это может вернуть тот же шаг или оставить Change в промежуточном состоянии.

Доработка:

- добавить `advance` после каждого успешно закрытого gate;
- либо заставить `next` явно возвращать Core action;
- проверить все single-step сценарии end-to-end.

## Schema v3

### V3-FIX-012 — Schema `$id` всё ещё указывают на v2

Все канонические schemas имеют адрес вида:

```text
https://deltafuse.dev/schemas/v2/...
```

При этом часть из них уже требует `schema_version: 3`. Тесты дополнительно закрепляют старый `/v2/`.

Доработка:

- изменить `$id` на `/schemas/v3/`;
- обновить bundled schemas;
- исправить tests;
- добавить проверку, что schema ID и поддерживаемая версия совпадают.

### V3-FIX-013 — Не все артефакты имеют явную версию v3

`change` и `evidence` требуют `schema_version: 3`, но task/slice и некоторые другие контракты не имеют обязательной версии.

Это мешает выполнить fail-closed правило для каждого артефакта.

Доработка:

- определить версию Change, task, slice, capability, routing, coverage, spec-delta, evidence и Decision;
- либо формально определить, какие артефакты наследуют версию Change;
- закрепить это schemas и документацией.

### V3-FIX-014 — Lock writer продолжает создавать schema_version 2

[`src/deltafuse/core/lock.py`](../src/deltafuse/core/lock.py) записывает `schema_version: 2`.

Это прямо противоречит DF3-008.

Доработка:

- выпустить lock contract v3;
- валидировать его отдельной schema;
- запрещать неподдерживаемые lock versions;
- синхронизировать installer и layout validators.

### V3-FIX-015 — Контекстный бюджет записан двумя значениями

Основной task contract использует `16000`, а qualification thresholds — `16384`.

Доработка:

- выбрать одно точное значение;
- предпочтительно оставить `16000`, поскольку оно уже используется schemas/templates;
- применить одинаковое значение в docs, runner и tests.

## Документация и терминология

### V3-FIX-016 — Каноническая документация продолжает описывать v2

В документации остаются:

- `schema_version: 2`;
- `framework.version: 2.5.0`;
- старые объяснения совместимости;
- прежние примеры конфигурации.

Доработка:

- выполнить полный поиск v2/2.5;
- классифицировать каждое совпадение как удаляемое или историческое;
- синхронно обновить EN и RU.

### V3-FIX-017 — Диаграммы используют удалённый `target_confirmed`

Английские диаграммы state machine переходят из `declaring` в `target_confirmed`, хотя таблицы и код используют `declared`.

Доработка:

- заменить остаточную терминологию;
- добавить автоматический тест на запрещённые lifecycle tokens.

### V3-FIX-018 — Документация всё ещё заявляет пять Human Gates

[`roles.md`](../docs/roles.md) перечисляет Capability Boundary, Decision, Specification, Scope Expansion и Final Integration.

План v3 фиксирует три Human Gates:

- Decision;
- specification acceptance;
- merge.

Доработка:

- разделить формальные Human Gates и обычные maintainer responsibilities;
- синхронизировать EN/RU;
- привести halt contract и роли к одной модели.

### V3-FIX-019 — Русская bench-документация неполна

В `bench.ru.md` отсутствуют полноценные таблицы Cases и Stage checks, присутствующие в английской версии. M03 не описан ни в одной версии.

Доработка:

- синхронизировать структуру разделов EN/RU;
- добавить M03;
- ввести автоматическую проверку паритета заголовков и таблиц.

### V3-FIX-020 — Главный Small-LLM contract находится только в backlog

Требования 35B A3B, 32k и qualification thresholds размещены преимущественно в `backlog/product/v3/**`. Но по правилам репозитория каноническая спецификация процесса должна находиться в `docs/**`.

Доработка:

- перенести нормативный Small-LLM Quality Contract в `docs/**`;
- оставить в backlog только статус и ссылки;
- добавить документ в `docs/README.md` и русскую версию.

## Distribution и инструменты

### V3-FIX-021 — Wheel smoke не закреплён воспроизводимым тестом

Существующий тест имитирует wheel mode через monkeypatch, но не:

- строит настоящий wheel;
- устанавливает его в чистый venv;
- запускает установленный CLI без checkout.

Release report утверждает, что smoke выполнялся, но отдельного сохраняемого evidence нет.

Доработка:

- добавить настоящий integration test build → install → CLI smoke;
- сохранить build manifest;
- проверять отсутствие зависимости от source checkout.

### V3-FIX-022 — `sync_assets.py --check` разрушителен

Скрипт игнорирует `--check` и начинает удалять `src/deltafuse/assets` перед регенерацией.

Доработка:

- реализовать настоящий read-only `--check`;
- генерировать bundle сначала во временный каталог;
- сравнивать manifest;
- заменять целевой каталог только после успешной генерации;
- добавить тест, что `--check` не меняет дерево.

### V3-FIX-023 — Qualification manifest может получить пустой commit

Runner выполняет `git rev-parse HEAD`, но не проверяет exit code. В текущей среде он вывел пустой `framework commit`.

Доработка:

- проверять exit code и непустой SHA;
- fail-closed завершать qualification при невозможности определить commit;
- записывать commit и content hash в каждый per-run report.

### V3-FIX-024 — Host probe недостаточен

Runner проверяет только доступность `/v1/models`, но не проверяет:

- загружена ли именно `ornith-1.5-35b-a3b`;
- установлен ли context limit 32768;
- выключен ли fallback;
- совпадают ли tokenizer/model parameters.

Доработка:

- получить `/v1/models`;
- проверить точный model ID;
- отправить диагностический запрос;
- записать host/model parameters в immutable manifest.

## Состояние программы

### V3-FIX-025 — Очередь и статусы программы противоречат друг другу

Сейчас:

- программа остаётся `active`;
- DF3-009 — `in-review`;
- release report — `pending-reference-runs`;
- строка «Брать в работу» ошибочно описывает DF3-009 как schema/Declare;
- в основном roadmap некоторые завершённые карточки не отмечены одинаково.

Доработка:

- не закрывать программу до прохождения qualification;
- исправить название текущего шага;
- после исправлений синхронно обновить DF3-009, index, release report и общий план.

### V3-FIX-026 — Рабочее дерево не чистое

Остались незакоммиченные изменения в шести файлах. До qualification невозможно однозначно определить, какая именно версия проверяется.

Доработка:

- разобрать и закоммитить либо исключить эти изменения;
- запускать qualification только на чистом фиксированном commit;
- записывать этот SHA в manifest.

## Implementation Order

1. V3-FIX-003, 012–015 — выровнять версию и schemas.
2. V3-FIX-009–011 — действительно передать state Core.
3. V3-FIX-004–008 — построить настоящий M03 и закрыть C-04.
4. V3-FIX-001, 023–024 — реализовать qualification runner.
5. V3-FIX-016–022 — синхронизировать docs, distribution и tooling.
6. V3-FIX-026 — получить чистый commit.
7. V3-FIX-002 — выполнить девять реальных прогонов.
8. V3-FIX-025 — синхронизировать статусы программы; только после этого закрывать DF3-009 и выпускать `3.0.0`.