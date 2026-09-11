# Процесс DeltaFuse

[English](README.md) | [**Русский**](README.ru.md)

DeltaFuse — specification-driven workflow, преобразующий сырой запрос в проверенный код через небольшие явно ограниченные контексты.

Две runtime-роли не смешивать: **Ядро** (исполняет Процесс) и **Воркер** (LLM или человек, который пишет файлы Change). Сам Процесс — lifecycle в [workflow.ru.md](./workflow.ru.md). См. [core-and-worker.ru.md](./core-and-worker.ru.md).

```text
Request -> Analyze -> Delta -> Fuse -> Converge
```

- **Change** — контейнер полного lifecycle.
- **Delta** — типизированный набор различий, вычисленный анализом.
- **Fuse** — применение Delta только к затронутым слоям артефактов.
- **Convergence** — доказательство согласованности claims, specification, tasks, tests и code.

## Каноническая граница

Эта директория является канонической только внутри репозитория DeltaFuse framework. Подключённый product repository не должен копировать `docs/**`.

Product pin-ит framework через:

```text
.deltafuse/config.yaml
.deltafuse/lock.yaml
```

Installer может генерировать repository-local skills для конкретных AI tools. Это неизменяемые snapshots с framework version, source и content hash, а не второй process source. Product-specific behavior остаётся за пределами framework.

## Источники истины

| Вопрос | Authoritative source в product repository |
|---|---|
| Как продукт должен себя вести | `docs/spec/**` |
| Какие вопросы и варианты рассматривались и почему | `docs/decisions/**` |
| Что и почему меняется сейчас | `docs/changes/<change-id>/**` |
| Какие исполнимые шаги нужны | `docs/changes/<change-id>/tasks/**` |
| Доказано ли поведение | Tests и evidence |
| Как поведение реализовано | Product code |
| Как работает DeltaFuse | Pinned external framework |

Только `docs/spec/**` является implementation law. Raw intake, Change request, Decisions, tasks, chat, diffs и archive не могут переопределять принятую specification.

## Lifecycle

```text
Intake
  -> Analyze
  -> Specify
  -> Decompose
  -> Declare
  -> Implement
  -> Verify
```

`Red` и `Green` являются состояниями evidence внутри Declare и Implement, а не шагами верхнего уровня.

## Product artifact layout

```text
product/
├── AGENTS.md
├── .deltafuse/
│   ├── config.yaml
│   └── lock.yaml
└── docs/
    ├── intake/
    ├── changes/
    │   └── <change-id>/
    │       ├── change.yaml
    │       ├── request.md
    │       ├── routing.yaml
    │       ├── analysis.md          # необязателен
    │       ├── slices/
    │       ├── tasks/
    │       ├── evidence/
    │       └── verification.md
    ├── spec/
    ├── decisions/
    └── archive/
        ├── intake/
        └── changes/
```

В product repository нет локальных `docs/process/`, `docs/init/` и `docs/todo/`. Bootstrap — profile, управляемый `project.baseline`; tasks принадлежат owning Change.

## Канонические документы

| Документ | Назначение |
|---|---|
| [core-and-worker.ru.md](./core-and-worker.ru.md) ([en](./core-and-worker.md)) | Ядро и воркер; Процесс — lifecycle, не роль |
| [workflow.md](./workflow.md) | Lifecycle, gates, bugs, Bootstrap и convergence |
| [state-machine.md](./state-machine.md) | Состояния Change, slice, task и Decision |
| [context-model.md](./context-model.md) | Domain routing, slicing и context contracts |
| [roles.md](./roles.md) | Границы полномочий ИИ и человека |
| [using.ru.md](./using.ru.md) | Установка и product integration |
| [bench.ru.md](./bench.ru.md) ([en](./bench.md)) | Агент-агностичный бенчмарк воркера (`deltafuse bench`); ядро считает диск |
| [contracts/board-snapshot.ru.md](./contracts/board-snapshot.ru.md) ([en](./contracts/board-snapshot.md)) | Снимок доски для fuse-map (`schema_version: 1`) |
| [contracts/halt.ru.md](./contracts/halt.ru.md) ([en](./contracts/halt.md)) | Кнопки хоста для `next --json` halt (`kind` + `choices`) |
| [contracts/leash.ru.md](./contracts/leash.ru.md) ([en](./contracts/leash.md)) | Конверт записи для `next --json` и `deltafuse leash` |

Исполняемые привязки воркера (LLM) — `process/skills/**`; машинный контракт Ядра — kernel. Схемы артефактов Change — в `process/schemas/**`. Схемы снимка доски, halt и leash — контракты совместимости с внешним UI/хостом (`docs/contracts/`), не схемы продукта; в consuming repository их не копировать.

