# Подключение DeltaFuse

[English](using.md) | [**Русский**](using.ru.md)

DeltaFuse устанавливается как versioned external framework. Product repository хранит product state и тонкий integration layer, но не копию канонической process documentation.

## Install

Из доверенного DeltaFuse checkout или package:

```powershell
./scripts/init.ps1 -TargetDir C:\path\to\product
```

```bash
bash ./scripts/init.sh /path/to/product
```

Installer создаёт без перезаписи существующих product files по умолчанию:

```text
.deltafuse/config.yaml
.deltafuse/lock.yaml
AGENTS.md
docs/intake/
docs/changes/
docs/spec/
docs/decisions/
docs/archive/intake/
docs/archive/changes/
```

Также ставит adapter skills в `.agents/skills/`, `.cursor/skills/` и `.gemini/skills/`. `adapters.mode`: `auto` (по умолчанию), `link` или `copy`.

- **link**, если checkout фреймворка лежит внутри продукта (git submodule или vendor path): каждый скилл — относительный symlink на `process/skills/<name>`. Cursor видит живые скиллы после `git submodule update`. `init --force` только обновляет `.deltafuse/lock.yaml`. Сами ссылки в git не коммитить. На Windows без права на symlink installer может сделать directory junction (абсолютный, только локально).
- **copy** в остальных случаях и если ОС отказывает в symlink: stamped snapshots с `DO NOT EDIT`, version, source URI и content hash.

Installer не создаёт `docs/process/`, `docs/init/` или `docs/todo/` внутри product repository.

## Pinning and upgrades

`.deltafuse/config.yaml` объявляет требуемую версию framework и project settings, включая `workflow.call_width` (`narrow` | `medium` | `wide`, по умолчанию `wide`). `.deltafuse/lock.yaml` фиксирует resolved version, schema version, framework content hash и профиль ширины вызова Analyze. После смены `call_width` перезапустите инсталлятор, чтобы lock совпал с config.

Повторный запуск installer с `-Force` (PowerShell) или `--force` (Bash) является явным framework upgrade. Он обновляет requested version в config и lock. Linked adapters следуют за nested checkout; copied adapters перегенерируются. Product-owned specification, Changes, Decisions, `AGENTS.md` и существующие templates сохраняются. До изменения lock:

1. Проверить active Changes и записанные в них framework/schema versions.
2. Завершить их на прежней версии либо закрыть Change.
3. Перезапустить installer и проверить product layout.

Нельзя вручную править adapter skills (копии или канонические файлы, на которые они ссылаются) и создавать локальный process fork. Product-specific routing и repository conventions находятся в `.deltafuse/config.yaml` и тонком product `AGENTS.md`.

## First operation

| Product state | Operation |
|---|---|
| Нет accepted specification baseline | Установить `project.baseline: draft`, выполнить `/intake`, затем Bootstrap через Analyze и Specify |
| Accepted specification существует | Установить `project.baseline: accepted`, создавать Changes через `/intake` |

Initial capability catalog предлагается ИИ и принимается человеком. После acceptance изменения capabilities требуют explicit catalog deltas.

Свежий `init` ставит `workflow.leash: off`, чтобы pet мог brainstorm. После `project.baseline: accepted` поставить `workflow.leash: enforce` и перезапустить installer (`deltafuse init --force`). Тогда появится локальный git `pre-commit`, который зовёт `deltafuse leash`, даже если воркер команду не набрал. Шаблон GitHub Action (`.github/workflows/deltafuse-leash.yml`) копируется один раз и необязателен. per-ankh и fuse-map включают `enforce` сами. `advisory` — hook отрабатывает, commit не валится. `off` — hook нет; сам `deltafuse leash` при нарушениях всё равно падает.

## Evidence ядра

Воркер пишет тесты и продуктовые файлы. Ядро записывает доказательство:

```text
deltafuse evidence <change-dir> --phase red --task TASK-001 --changed-path tests/test_foo.py -- pytest tests/test_foo.py -q
```

Import/syntax и Red с `_` не authentic. Ядро ставит штамп на YAML; `check-gate --gate targeting` отвергает schema-valid файл, который написали не через `deltafuse evidence`.

## Coverage ядра

После routing и одного среза на primary capability Ядро пишет матрицу claims. Воркер не hand-write `coverage.yaml`:

```text
deltafuse coverage <change-dir>
```

Затем `check-gate --gate analyzed`. Повтор сохраняет уже записанные `tasks` / `evidence` / `status`.

## Specify по одному срезу

После Analyze `deltafuse next --step specify` называет один неспецифицированный срез. Пишите только его `spec_refs`. Не загружайте всё дерево `docs/spec/**`. Когда все срезы `specified`, `specify_pass` = `close`: `check-gate --gate specified`. Не закрывайте гейт Change на середине набора.

## Следующая работа

Change id не обязателен: Ядро берёт первый ready элемент.

```text
deltafuse next
deltafuse next --list
deltafuse next --human
deltafuse next --step declare --json
deltafuse decide <change-dir> --decision DEC-0001 --status accepted
deltafuse decide <change-dir> --spec --status accepted
```

`--human` — тот же шаг для человеческого воркера: glob чтения/записи, `evidence` где нужно, затем `check-gate`. Не второй процесс. `deltafuse decide` — единственный писатель `accepted`/`rejected` у DEC и spec; правка frontmatter гейт не закрывает.

Точка входа LLM по умолчанию — `/run` (сквозной режим): `deltafuse next`, загрузить skill, продолжить в той же сессии. Не ждать вставленных `/analyze` … `/verify`. Когда `next --json` даёт `halt.kind` `decision` или `spec`, показать `halt.choices` кнопками хоста по [контракту halt](./contracts/halt.ru.md), ждать, выполнить только `choice.command`. `inspect` (`command: null`) — стоп. Одношаговые skills — чтобы после сбоя перезапустить один шаг.

Сгенерированные skills привязывают воркера к LLM: пишут файлы Change, закрывают шаг через `check-gate`, затем `deltafuse next` в этой же сессии. Следующую слеш-команду сами не выбирают.

Пустая очередь — ненулевой exit, в выводе blocked (DEC, spec gate) и `halt.choices`, либо halt `done`, если нового intake нет.

## Бенчмарк воркера

Ставится песочница продукта, любой воркер заполняет дерево, **судья** считает диск с `--pack`. Модель из CLI не вызывается. Воркер не запускает `bench score`. Попытки — из журнала ядра, не из самоотчёта воркера.

```text
deltafuse bench init M02-policy-stats <product-dir>
deltafuse bench journal <product-dir>
deltafuse bench score <product-dir> --pack <framework-or-pack> --json --label cursor+opus-5 --out-file ../scores/opus.json
deltafuse bench compare ../scores/opus.json ../scores/flash.json
```

См. [bench.ru.md](./bench.ru.md). Оракул и hidden-тесты остаются в пакете фреймворка.

## Halt хоста

`deltafuse next --json` `halt` — контракт кнопок хоста ([halt.ru.md](./contracts/halt.ru.md)). Показать каждый `choices[].label`. Выполнить только `choice.command` из корня продукта. `inspect` (`command: null`) — стоп. Не добавлять кнопки merge / `git push`. Ядро UI не рисует.

## Конверт записи

`deltafuse next --json` `envelope` — список путей, куда воркер может писать ([leash.ru.md](./contracts/leash.ru.md)). Хост MUST резать write-tools по `envelope.write`. Если не умеет — `/run` всё равно зовёт `deltafuse leash` перед концом шага (не замена hook). `deltafuse leash` сверяет git-дифф (или `--file`) с готовыми envelope. Intake не пишет `src/**`. `envelope: null` плюс грязный `src/**` / `tests/**` — orphan, команда падает. При `halt.kind` `decision` или `spec` envelope пустой, запись в код продукта выключена. `docs/spec/**` — orphan только после `project.baseline: accepted`. `docs/intake/**` и `AGENTS.md` не orphan. `workflow.leash: advisory` — те же нарушения, exit 0. `enforce` ставит git hook и (по желанию) CI; `off` — нет. UI fuse-map и кнопки Cursor живут вне `src/deltafuse/**`.

```text
deltafuse leash <product-root>
deltafuse leash <product-root> --file src/foo.py
```

## Внешние доски

Read-only UI (fuse-map) обязан читать [контракт снимка доски](./contracts/board-snapshot.ru.md) и для карточек, и для колонок/шагов (`layout`). Нельзя разбирать `docs/changes/**` и хардкодить lifecycle. Installer не копирует `docs/contracts/**` в продукт. fuse-map пинит `schema_version` у себя. Этот репозиторий UI доски не содержит.

```text
deltafuse board <product-root> --json
deltafuse board <product-root> --json --archive
```

Stdout — один JSON. Файлы продукта не пишутся. Нет `.deltafuse/lock.yaml` — ошибка, не пустая доска.
