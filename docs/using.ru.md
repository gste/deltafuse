# Подключение DeltaFuse

[English](using.md) | [**Русский**](using.ru.md)

DeltaFuse устанавливается как versioned external framework. Product repository хранит product state и тонкий integration layer, но не копию канонической process documentation.

## Install

> **DF3-005**: two supported channels — nested source checkout (`vendor/deltafuse`) or a wheel. The wheel ships the immutable runtime asset bundle (schemas, templates, skills) and needs no source checkout. Scaffold new Changes with `deltafuse new <change-id> --route code|docs|ops` — it never closes Intake. Upgrades fail closed while active Changes exist; evidence stamps are never re-signed.

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
docs/intake/
docs/changes/
docs/spec/
docs/decisions/
docs/archive/intake/
docs/archive/changes/
```

Также ставит adapter skills в `.agents/skills/`, `.cursor/skills/` и `.gemini/skills/`. `adapters.mode`: `auto` (по умолчанию), `link` или `copy`.

### Host instructions

`AGENTS.md` и `AGENTS.override.md` — необязательная integration surface, которой владеет host. По умолчанию DeltaFuse не создаёт и не меняет ни один из них. В интерактивном terminal `init` спрашивает способ интеграции; в CI/non-interactive режиме оба файла сохраняются, а явная активация выполняется через `/run` или `deltafuse next --json`. Детерминированный выбор: `--agents-md=bridge|preserve|replace`. `bridge` добавляет один короткий размеченный bridge в effective file (`AGENTS.override.md` имеет приоритет); `replace` заменяет существующий effective file и в интерактивном режиме требует второго подтверждения. Полный Worker contract остаётся в generated `run` и lifecycle skills.

- **link**, если checkout фреймворка лежит внутри продукта (git submodule или vendor path, рекомендуется `vendor/deltafuse`): каждый скилл — относительный symlink на `process/skills/<name>`. Cursor видит живые скиллы после `git submodule update`. `init --force` только обновляет `.deltafuse/lock.yaml`. Сами ссылки в git не коммитить. На Windows без права на symlink installer может сделать directory junction (абсолютный, только локально).
- **copy** в остальных случаях и если ОС отказывает в symlink: stamped snapshots с `DO NOT EDIT`, version, source URI и content hash.

Installer не создаёт `docs/process/`, `docs/init/` или `docs/todo/` внутри product repository.

## Pinning and upgrades

Всё, чем владеет Ядро, пишется `deltafuse` без дефиса: CLI, Python-пакет, пин продукта `.deltafuse/` и git slug (`gste/deltafuse`). Nested checkout класть в `vendor/deltafuse`, чтобы путь clone и `source` в `lock.yaml` совпадали. Сабмодуль не класть в `.deltafuse/` — это каталог пина, не checkout.

```bash
git submodule add https://github.com/gste/deltafuse.git vendor/deltafuse
```

`.deltafuse/config.yaml` объявляет требуемую версию framework и project settings, включая `workflow.call_width` (`narrow` | `medium` | `wide`, по умолчанию `wide`). `.deltafuse/lock.yaml` фиксирует resolved version, schema version, framework content hash и профиль ширины вызова Analyze. После смены `call_width` перезапустите инсталлятор, чтобы lock совпал с config.

Для framework release файл `VERSION` является единственным machine-readable источником версии. Package metadata читает его динамически, а installer templates содержат schema-valid marker `0.0.0`, который каждый installer заменяет значением из `VERSION`. Поэтому version bump меняет `VERSION` и человекочитаемую release-запись в `CHANGELOG.md`; generated assets синхронизируются без встраивания номера релиза.

Повторный запуск installer с `-Force` (PowerShell) или `--force` (Bash) является явным framework upgrade. Он обновляет requested version в config и lock. Linked adapters следуют за nested checkout; copied adapters перегенерируются. Product-owned specification, Changes, Decisions, host instruction files и существующие templates сохраняются. До изменения lock:

1. Проверить active Changes и записанные в них framework/schema versions.
2. Завершить их на прежней версии либо закрыть Change.
3. Перезапустить installer и проверить product layout.

Нельзя вручную править adapter skills (копии или канонические файлы, на которые они ссылаются) и создавать локальный process fork. Product-specific routing и repository conventions находятся в `.deltafuse/config.yaml` и, если host выбрал его, собственном тонком `AGENTS.md`.

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

Import/syntax и Red с `_` не authentic. Ядро ставит штамп на YAML; `check-gate --gate declaring` отвергает schema-valid файл, который написали не через `deltafuse evidence`.

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

**Пароль Human Gate (опционально).** `deltafuse gate-password set` хранит солёный хэш PBKDF2 в `.deltafuse/gate-password.yaml` (файл ядра: leash отвергает его в diff воркера). После этого `decide` спрашивает пароль в терминале до любой записи и отказывает, если stdin — не терминал; флага или переменной окружения для пароля нет. Каждый receipt пишет `human_check: password` или `none`. `gate-password clear` и смена требуют текущий пароль; `gate-password status` показывает, включён ли он. Пароль закрывает команду `decide`, а не журнал: от модели, подделывающей файлы руками, защищает изоляция воркера на хосте.

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

## Artifact Writer

Ядро предоставляет управляемую схемам службу сериализации и валидации для артефактов пакетов Change ([artifact-writer.ru.md](./contracts/artifact-writer.ru.md)).

### Практические примеры использования

```text
# Проверить поддерживаемые свойства и схемы через инспекцию возможностей
deltafuse artifact describe --kind task --operation create

# Создать новый артефакт Change из JSON-структуры
deltafuse artifact create --kind task --change docs/changes/CHG-101 --input input.json

# Атомарно обновить артефакт через JSON Pointer patch с проверкой SHA256 целого файла
deltafuse artifact update --kind task --change docs/changes/CHG-101 --target tasks/TASK-001.md --expected-sha256 <sha> --input patch.json

# Выполнить read-only валидацию схемы и ссылок без изменения диска
deltafuse artifact validate --kind task --change docs/changes/CHG-101 --target tasks/TASK-001.md --json

# Обновить дочерний индекс родительского Change после создания/обновления задачи/среза
deltafuse artifact update-index --change docs/changes/CHG-101 --child-kind task --child-id TASK-001
```

### Обнаружение возможностей и совместимость
Клиенты определяют доступность Artifact Writer с помощью `deltafuse artifact describe --kind <kind> --operation <op>`.

**Путь воркера — `artifact write`** (п. 1 роадмапа). Воркер пишет структуру только через Writer: прозу (тело) и поля, а `id`, `change`, `status`, `context_budget` задачи, сам файл и индекс в `change.yaml` пишет ядро: `deltafuse artifact write --kind task --change docs/changes/CHG-101 --input task.json`, где `task.json` — `{"identity": "TASK-001", "fields": {...}, "body": "проза"}`. Файла нет — создаётся; есть — меняются только названные поля, ожидаемый sha256 ядро берёт само. Списки `spec-delta` сливаются по слайсам, проза дописывается. Хост с вызовом функций отдаёт тот же вход как типизированный инструмент. Виды: `task`, `slice`, `routing`, `spec-delta`, `change`. Leash отвергает `routing.yaml`, `spec-delta.md`, слайс или задачу, байты которых не породили ни Writer, ни ядро (`deltafuse state`, `decide`).

### Ручное создание и существующие артефакты
Существующие артефакты никогда автоматически не перезаписываются и не мигрируют массово; Writer читает файлы, созданные вручную. Новые записи `routing.yaml`, `spec-delta.md`, слайсов и задач идут через Writer: leash судит только то, что изменилось с его базы, поэтому уже закоммиченные артефакты не затронуты.

### Явное подтверждение каноникализации
Для переформатирования или нормализации метаданных неканоничных артефактов требуется явный флаг `--canonicalize-metadata` вместе с проверкой хэша файла. Без явного согласия формативные правки метаданных не применяются.

### Процедура восстановления транзакций
В случае сбоя или прерывания процесса при операциях создания/обновления Ядро проверяет `.deltafuse/journal/` под блокировкой `ProductMutationLock`. Незавершённые транзакции со статусом `prepared` восстанавливают исходный файл, а транзакции со статусом `published` завершают запись чека receipt и публикации.



## Внешние доски

Read-only UI (fuse-map) обязан читать [контракт снимка доски](./contracts/board-snapshot.ru.md) и для карточек, и для колонок/шагов (`layout`). Нельзя разбирать `docs/changes/**` и хардкодить lifecycle. Installer не копирует `docs/contracts/**` в продукт. fuse-map пинит `schema_version` у себя. Этот репозиторий UI доски не содержит.

```text
deltafuse board <product-root> --json
deltafuse board <product-root> --json --archive
```

Stdout — один JSON. Файлы продукта не пишутся. Нет `.deltafuse/lock.yaml` — ошибка, не пустая доска.




## Восстановление

- Change завис между валидацией и переходом: повторите `deltafuse advance <change> --gate <gate>` — последний receipt авторитетен, незавершённая запись статуса будет завершена.
- Статус, расходящийся с последним receipt, останавливает очередь: закройте или мигрируйте Change, либо верните артефакт в Core через `advance`. Ручные правки не мигрируются.
- Артефакты неподдерживаемых версий схем останавливаются с диагностикой `schema_version` и остаются нетронутыми; мигрируйте вручную на v3.
- Версионирование артефактов (V3-FIX-013): `change`, `evidence` и каталог capabilities несут явный `schema_version: 3`. Вложенные в Change артефакты (`tasks/**`, `slices/**`, `decisions/**`, frontmatter `spec-delta`, `routing.yaml`, `coverage.yaml`) наследуют версию родительского Change — собственного `schema_version` у них нет, и они валидируются fail-closed через контракт Change.
- Проверяйте весь продуктовый контракт в любой момент: `deltafuse validate-config .`.
- Human Gate клики живут в `.deltafuse/gate-journal.jsonl` (Core-owned): пересборки обнаруживаются. Профиль `broker-signed` удалён (его ключ лежал в репозитории); используйте пароль Human Gate.
