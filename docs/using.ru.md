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

Также генерируются tool-specific skill snapshots в `.agents/skills/`, `.cursor/skills/` и `.gemini/skills/`. Каждый snapshot помечен `DO NOT EDIT` и содержит installed framework version, source и content hash.

Installer не создаёт `docs/process/`, `docs/init/` или `docs/todo/` внутри product repository.

## Pinning and upgrades

`.deltafuse/config.yaml` объявляет требуемую версию framework и project settings, включая `workflow.call_width` (`narrow` | `medium` | `wide`, по умолчанию `wide`). `.deltafuse/lock.yaml` фиксирует resolved version, schema version, framework content hash и профиль ширины вызова Analyze. После смены `call_width` перезапустите инсталлятор, чтобы lock совпал с config.

Повторный запуск installer с `-Force` (PowerShell) или `--force` (Bash) является явным framework upgrade. Он обновляет requested version в config, lock и generated adapters, но сохраняет product-owned specification, Changes, Decisions, `AGENTS.md` и остальные существующие templates. До изменения lock:

1. Проверить active Changes и записанные в них framework/schema versions.
2. Завершить их на прежней версии либо закрыть Change.
3. Перегенерировать adapters и проверить product layout.

Нельзя вручную редактировать generated skills и создавать локальный process fork. Product-specific routing и repository conventions находятся в `.deltafuse/config.yaml` и тонком product `AGENTS.md`.

## First operation

| Product state | Operation |
|---|---|
| Нет accepted specification baseline | Установить `project.baseline: draft`, выполнить `/intake`, затем Bootstrap через Analyze и Specify |
| Accepted specification существует | Установить `project.baseline: accepted`, создавать Changes через `/intake` |

Initial capability catalog предлагается ИИ и принимается человеком. После acceptance изменения capabilities требуют explicit catalog deltas.

## Evidence ядра

Воркер пишет тесты и продуктовые файлы. Ядро записывает доказательство:

```text
deltafuse evidence <change-dir> --phase red --task TASK-001 --changed-path tests/test_foo.py -- pytest tests/test_foo.py -q
```

Import/syntax и Red с `_` не authentic. `check-gate --gate targeting` по-прежнему проверяет YAML на диске.

## Следующая работа

Change id не обязателен: ядро берёт первый ready элемент.

```text
deltafuse next
deltafuse next --list
deltafuse next --step declare --json
```

Пустая очередь — ненулевой exit, в выводе blocked (DEC, spec gate) или `/intake`.

## Внешние доски

Read-only UI (fuse-map) обязан читать [контракт снимка доски](./contracts/board-snapshot.ru.md) и для карточек, и для колонок/шагов (`layout`). Нельзя разбирать `docs/changes/**` и хардкодить lifecycle. Installer не копирует `docs/contracts/**` в продукт. fuse-map пинит `schema_version` у себя.
