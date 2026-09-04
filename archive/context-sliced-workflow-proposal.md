# Context-Sliced Workflow Proposal

> Status: accepted design baseline for DeltaFuse 2.0. Канонические исполнимые правила находятся в `workflow.md`, `state-machine.md`, `context-model.md`, `roles.md`, `skills/**` и `schemas/**`.

## Purpose

Цель процесса — преобразовывать сырой пользовательский запрос в проверенное изменение кода через последовательность небольших, явно связанных артефактов. Каждый шаг получает только необходимый ему контекст, чтобы работу можно было надёжно выполнять небольшой локальной LLM.

Короткая продуктовая формула DeltaFuse:

```text
Request -> Analyze -> Delta -> Fuse -> Verify
```

Полная процессная цепочка:

```text
Raw intent
    -> Normalized request
    -> Analyzed change
    -> Bounded delta
    -> Accepted specification
    -> Executable task decomposition
    -> Failing executable test
    -> Implementation
    -> Convergence proof
```

Основной принцип:

> Каждый skill получает минимальный контекст, но каждый переход между слоями оставляет проверяемый артефакт с точными ссылками на источник.

## DeltaFuse Semantics

Название `DeltaFuse` сохраняет исходную идею, но расширяет её за пределы обязательного изменения спецификации.

```text
Change Request -> Analyze -> Delta -> Fuse -> Converge
```

- `Change Request` сообщает, чего хочет или что наблюдает пользователь.
- `Analyze` сопоставляет запрос с текущей spec и состоянием системы.
- `Delta` описывает минимальное проверяемое расхождение между текущим и требуемым состоянием.
- `Fuse` применяет delta ко всем затронутым слоям: spec, decisions, tasks, tests и code.
- `Converge` доказывает, что после применения delta артефакты снова согласованы.

`Change` и `Delta` не являются синонимами:

> Change — контейнер полного жизненного цикла. Delta — вычисленный анализом набор различий, которые необходимо применить.

Raw request ещё не является delta: до анализа неизвестно, действительно ли запрос требует изменения, затрагивает ли он spec и соответствует ли заявленный bug фактическому расхождению.

Один Change может содержать несколько связанных slice-level deltas:

```text
CHG-100
├── SLICE-01 / DELTA-01: authentication requirements
├── SLICE-02 / DELTA-02: session conformance
└── SLICE-03 / DELTA-03: audit integration
```

Внешний интерфейс должен оставаться простым и оперировать `change`. Типизированные deltas являются внутренним результатом Analyze и не требуют от пользователя ручной классификации.

## Terminology

### Artifact Layers

Слой артефактов отвечает за определённый тип информации:

| Layer | Responsibility |
|---|---|
| Raw intake | Исходные сообщения, документы, логи и наблюдения пользователя |
| Change | Формализованное намерение и результаты анализа конкретного изменения |
| Specification | Нормативное описание требуемого поведения продукта |
| Decision | Продуктовые и технические вопросы, варианты, решения и rationale |
| Task | Исполнимая декомпозиция изменения |
| Tests | Исполняемые доказательства поведения и регрессий |
| Code | Реализация требований |
| Evidence | Результаты Red, Green и итоговой верификации |

### Product Domains and Capabilities

Artifact layers нельзя смешивать с продуктовыми доменами. Продуктовая декомпозиция имеет вид:

```text
Product domain
    -> Capability
        -> Requirement
            -> Scenario
```

Пример:

```text
identity
    -> authentication
    -> session-management
    -> access-control

payments
    -> invoicing
    -> payment-processing
    -> refunds
```

Конкретные домены и capabilities нельзя заранее перечислить в DeltaFuse. Фреймворк задаёт их метамодель, формат repository-local каталога и правила контролируемого расширения.

### Core Terms

- `Change` — адресуемый пакет артефактов и state machine одного пользовательского изменения от Intake до Archive.
- `Change request` — формализация сырого запроса без проверки против spec и без технического решения. Это не принятое требование и не разрешение на реализацию.
- `Change analysis` — результат сопоставления change request с принятой spec, decisions и границами capabilities.
- `Delta` — ограниченное, типизированное и проверяемое различие между текущим и требуемым состоянием, полученное в результате Change analysis.
- `Fuse` — управляемое применение delta только к затронутым artifact layers с соблюдением gates и traceability.
- `Convergence` — подтверждённое состояние, в котором claims, spec, tasks, tests и code согласованы.
- `Slice` — независимо анализируемая и проверяемая часть change с одним основным результатом и одной owning capability.
- `Task` — минимальная исполнимая единица реализации. Task ссылается на требования и добавляет только операционные ограничения и Definition of Done.
- `Evidence` — компактная запись проверочного запуска, достаточная для подтверждения результата без секретов и лишних runtime-данных.

## Sources of Truth

Single source of truth применяется отдельно к каждому виду информации.

| Question | Authoritative source |
|---|---|
| Как система должна вести себя | `docs/spec/**` |
| Какой вопрос рассматривался и почему принято решение | `docs/decisions/**` |
| Что именно сейчас меняется и почему | `docs/changes/<change-id>/**` |
| Какие шаги должны быть выполнены | `docs/changes/<change-id>/tasks/**` |
| Подтверждено ли поведение | Автоматические тесты и evidence |
| Как поведение реализовано | Product code |
| Как работает сам процесс DeltaFuse | Установленный и pinned DeltaFuse framework |

Только `docs/spec/**` является нормативным источником продуктового поведения. Change, tasks, decisions, чат, raw intake и archive не могут переопределять принятую spec.

Change-артефакты могут содержать краткое ненормативное описание ожидаемого поведения, но обязаны указывать точные `spec_refs`. При расхождении выигрывает `docs/spec/**`.

## Framework and Product Boundary

DeltaFuse состоит из двух принципиально разных областей владения:

1. DeltaFuse framework repository хранит алгоритм обработки изменений.
2. Product repository хранит состояние конкретного продукта и его changes.

Канонические process rules нельзя вручную копировать в каждый product repository. Иначе каждая копия превращается в независимый fork процесса, теряет связь с версией framework и начинает расходиться с skills, schemas и validators.

Граница формулируется так:

> Product repository хранит состояние продукта. DeltaFuse framework хранит алгоритм обработки этого состояния.

### DeltaFuse Framework Repository

Целевая структура самого DeltaFuse:

```text
delta-fuse/
├── docs/
│   ├── workflow.md
│   ├── roles.md
│   ├── context-model.md
│   ├── state-machine.md
│   ├── using.md
│   └── README.md
├── process/
│   ├── skills/
│   │   ├── intake/
│   │   ├── analyze-change/
│   │   ├── specify-change/
│   │   ├── decompose-change/
│   │   ├── target-task/
│   │   ├── implement-task/
│   │   └── verify-change/
│   ├── schemas/
│   │   ├── change.schema.yaml
│   │   ├── capability.schema.yaml
│   │   ├── decision.schema.yaml
│   │   ├── task.schema.yaml
│   │   └── evidence.schema.yaml
│   └── templates/
├── scripts/
└── tests/
```

Framework repository является единственным каноническим источником:

- lifecycle и state machine;
- ролей и human gates;
- contracts всех skills;
- schemas артефактов;
- context assembly rules;
- templates, validators и migrations;
- upgrade semantics.

### Product Repository Integration

Product repository содержит только тонкую интеграцию с framework:

```text
product/
├── AGENTS.md
├── .deltafuse/
│   ├── config.yaml
│   └── lock.yaml
└── docs/
    ├── intake/
    ├── changes/
    ├── spec/
    ├── decisions/
    └── archive/
```

Минимальный `.deltafuse/config.yaml`:

```yaml
framework:
  source: plugin
  version: 2.0.0

paths:
  intake: docs/intake
  changes: docs/changes
  specification: docs/spec
  decisions: docs/decisions
  archive: docs/archive

context:
  max_tokens: 16000
  max_files: 24

project:
  baseline: accepted
  capability_catalog: docs/spec/_capabilities.yaml
```

`.deltafuse/lock.yaml` фиксирует реально используемую версию и совместимость schemas:

```yaml
framework:
  version: 2.0.0
  schema_version: 2
  content_hash: sha256:<framework-content-hash>
```

Активный Change должен обрабатываться одной pinned-версией process semantics. Поэтому `change.yaml` записывает framework version и schema version, использованные при Intake. Framework upgrade выполняется как отдельная управляемая операция с migration check; активный Change либо завершается на прежней версии, либо явно мигрируется целиком.

### Thin `AGENTS.md` Adapter

Product-level `AGENTS.md` содержит только repository-specific instructions и точку подключения к pinned DeltaFuse:

```markdown
# Agent Instructions

This repository uses the DeltaFuse version pinned in `.deltafuse/lock.yaml`.

Product behavior: `docs/spec/**`.
Active changes: `docs/changes/**`.
Project configuration: `.deltafuse/config.yaml`.

Load the pinned DeltaFuse workflow before running a lifecycle operation.
Do not implement directly from chat or raw intake.
```

Полные process rules не дублируются в `AGENTS.md`.

### Generated Agent Adapters

Некоторые AI-инструменты обнаруживают только repository-local skills. Для них installer может создавать adapters в `.agents/skills/**`, `.cursor/skills/**` или аналогичной директории.

Такие файлы:

- являются generated artifacts, а не canonical process source;
- помечаются `DO NOT EDIT`;
- содержат framework version, source и content hash;
- обновляются только DeltaFuse installer/update command;
- валидируются против `.deltafuse/lock.yaml`;
- либо делегируют выполнение установленному framework, либо являются его проверяемым generated snapshot.

Пример metadata:

```yaml
generated_by: deltafuse@2.0.0
source: deltafuse://skills/intake
content_hash: sha256:<skill-content-hash>
```

Канонически process всё равно живёт только в DeltaFuse framework, даже когда для совместимости создаётся repo-local adapter. Для product repository framework является versioned external dependency, а не частью product documentation.

## Proposed Product Repository Layout

```text
product/
├── AGENTS.md
├── .deltafuse/
│   ├── config.yaml
│   └── lock.yaml
└── docs/
    ├── intake/
    │   └── <raw-input>
    ├── changes/
    │   ├── README.md
    │   └── <change-id>/
    │       ├── change.yaml
    │       ├── request.md
    │       ├── routing.yaml
    │       ├── analysis.md
    │       ├── slices/
    │       │   └── <slice-id>.md
    │       ├── spec-delta.md
    │       ├── design.md
    │       ├── tasks/
    │       │   └── TASK-NNN-<slug>.md
    │       ├── coverage.yaml
    │       ├── evidence/
    │       │   ├── red/
    │       │   └── green/
    │       └── verification.md
    ├── spec/
    │   ├── README.md
    │   ├── _capabilities.yaml
    │   ├── context.md
    │   ├── policies/
    │   └── <domain>/
    │       ├── README.md
    │       └── <capability>.md
    ├── decisions/
    │   └── DEC-NNNN-<slug>.md
    └── archive/
        ├── intake/
        └── changes/
```

Optional-файлы создаются только при необходимости:

- `spec-delta.md` — при изменении требований;
- `design.md` — при архитектурной, междоменной, миграционной, security- или performance-сложности;
- несколько slice-файлов — если change не помещается в один безопасный контекст;
- отдельные evidence-файлы — если запись в task/change становится слишком большой.

`docs/` отсутствует в product repository. `docs/init/` и `docs/todo/` также отсутствуют:

- Bootstrap является workflow profile, а не artifact layer;
- Task является дочерней сущностью Change, а не глобальным состоянием `todo`;
- task state хранится в metadata, а не кодируется перемещением между `todo`, `doing` и `done`.

`docs/changes/README.md` является компактным активным индексом и может генерироваться из `change.yaml`/task metadata. Он не является вторым источником статусов.

### Naming Policy

1. Папки называются по устойчивым сущностям, а не временным состояниям.
2. Коллекции используют множественное число: `changes/`, `decisions/`, `tasks/`.
3. Концептуальный единый пакет сохраняет привычное имя `spec/`.
4. Lifecycle status хранится в metadata.
5. Только `archive/` физически отделяет неактивный контекст.
6. `intake/` предпочтительнее `input/`: это вход инженерного процесса, а не runtime/test input продукта.
7. `decisions/` предпочтительнее `adr/`, потому что содержит решения нескольких видов, а не только архитектурные ADR.

## Decision Model

`docs/decisions/**` хранит вопросы, варианты, решения и rationale, которые нельзя надёжно вывести только из требований. Architecture Decision Record является частным случаем общего Decision Record.

Decision-файл можно открыть до появления ответа: тогда это адресуемый product/technical question со `status: proposed`. Папка `decisions/` тем самым описывает полный lifecycle выбора, а не только архив уже принятых архитектурных ADR. Уточнения дополняют record и его варианты; принятие, отклонение или supersede меняют status, не уничтожая историю вопроса.

```yaml
id: DEC-0002
kind: product
status: proposed
change: CHG-042
affects:
  capabilities:
    - identity.session-management
  spec_refs:
    - docs/spec/identity/session-management.md#REQ-SESSION-017
```

Допустимые kinds:

```yaml
kind: product | architecture | integration | policy | operational
```

Lifecycle:

```yaml
status: proposed | accepted | rejected | superseded
```

Decision Record должен содержать:

- вопрос и контекст;
- варианты и существенные trade-offs;
- принятое решение либо причину rejection;
- rationale и последствия;
- owner/human gate;
- affected capabilities;
- существующие или будущие spec refs;
- supersedes/superseded-by, если решение заменяет другое.

Непринятый product question может храниться как `status: proposed`, но не становится требованием. После принятия любое решение, влияющее на observable behavior, contract, policy или обязательный invariant, должно быть отражено шагом Specify в `docs/spec/**`.

Accepted, rejected и superseded decisions сохраняются в `docs/decisions/**`: они объясняют историю выбора и не являются временной очередью. Decision не заменяет spec и не является самостоятельным implementation law.

`change.yaml` и `request.md` обязательны для каждого change. `change.yaml` является компактным управляющим корнем, а не ещё одной содержательной спецификацией.

## Change Package Root

### `change.yaml`

Ключевой процессной сущностью DeltaFuse является `Change`, а его управляющим файлом — `docs/changes/<change-id>/change.yaml`.

Он содержит идентичность, состояние, классификацию, вычисленную delta и ссылки на дочерние артефакты, но не копирует их полное содержимое:

```yaml
schema_version: 2
id: CHG-042
title: Refresh expired session
status: specified

framework:
  version: 2.0.0
  content_hash: sha256:<framework-content-hash>

intent: bugfix
risk: medium

source:
  request: request.md

analysis:
  routing: routing.yaml
  summary: analysis.md

deltas:
  - id: DELTA-01
    slice: SLICE-01
    kind: conformance
    summary: Session refresh не соответствует REQ-SESSION-017.
    specification:
      operation: none
      refs:
        - docs/spec/identity/session-management.md#REQ-SESSION-017
    tests:
      operation: add
    tasks:
      operation: derive
    implementation:
      operation: modify
    evidence:
      operation: record

slices:
  - id: SLICE-01
    status: specified
    file: slices/SLICE-01.md

decisions: []
spec_delta: none
design: none
tasks: []
verification: null
```

`change.yaml` позволяет оркестратору определить следующий допустимый шаг, а локальной LLM — загрузить только указанные артефакты.

### `request.md`

`request.md` является первым содержательным артефактом и корнем provenance, но не implementation law. После Intake его базовые claims считаются immutable.

Позднее уточнение пользователя добавляется как revision, а не переписывает историю молча:

```markdown
## Revision 2

- Supersedes: CR-002
- CR-004: Сессия обновляется только при валидном refresh token.
```

Downstream-этапы связаны с Change ID, но не обязаны читать `request.md` целиком. Tasks создаются из analyzed slice, accepted spec и optional design, а не напрямую из request.

## Classification Axes

Change классифицируется по независимым осям. Отсутствие spec delta ничего не говорит о сложности или риске.

```yaml
intent: feature | bugfix | refactor | maintenance | documentation
delta_kind: requirements | conformance | structural | operational | mixed
requirement_delta: none | added | modified | removed | mixed
design_impact: local | cross-cutting | architectural
risk: low | medium | high | critical
size: small | medium | large
```

| Situation | intent | delta_kind | requirement_delta | design_impact |
|---|---|---|---|---|
| Код противоречит существующему требованию | `bugfix` | `conformance` | `none` | Любой |
| Пользователь ожидает неописанное поведение | `feature` или `bugfix` | `requirements` | `added` или `modified` | Любой |
| Чистый рефакторинг | `refactor` | `structural` | `none` | Обычно `local` |
| Новый сервис | `feature` | `requirements` или `mixed` | `added` | Обычно `architectural` |

Классификацию `trivial` не следует использовать как синоним `requirement_delta: none`: критический concurrency bug может не менять требования.

### Typed Delta

Delta описывается как набор проекций на artifact layers. Каждая предусмотренная схемой проекция указывается явно; `operation: none` доказывает, что слой рассмотрен и признан незатронутым.

```yaml
delta:
  kind: requirements | conformance | structural | operational | mixed
  specification:
    operation: none | add | modify | remove | mixed
  catalog:
    operation: none | add | modify | remove
  decisions:
    operation: none | propose | supersede
  tests:
    operation: none | add | modify | remove
  tasks:
    operation: none | derive | modify | remove
  implementation:
    operation: none | add | modify | remove | mixed
  evidence:
    operation: none | record
```

Типовые случаи:

| Change | Semantic delta | Fuse path |
|---|---|---|
| Feature | Требуемого поведения нет в spec | Spec -> Tasks -> Tests -> Code |
| Implementation bug | Реализация не соответствует существующей spec | Tasks -> Tests -> Code |
| Specification bug | Spec неполна или неверна | Spec -> Tasks -> Tests -> Code, если code тоже затронут |
| Refactor | Структура code меняется при нулевой behavioral delta | Tasks -> invariant tests -> Code |
| Documentation/operations | Меняется только соответствующий ненормативный слой | Только объявленные layers |

Fuse не означает обязательное изменение каждого слоя. Он применяет delta ко всем затронутым слоям и доказывает, что незатронутые invariants сохранились.

## Capability Model

### Framework-Level Metamodel

DeltaFuse фиксирует только универсальные классы:

- product domain;
- capability;
- requirement;
- scenario;
- cross-cutting policy;
- integration boundary;
- external system;
- actor;
- data ownership.

Допустимые типы capabilities как аналитическая подсказка:

- business capability;
- supporting capability;
- integration capability;
- data/state management;
- cross-cutting policy;
- operational capability.

Это не готовый перечень доменов и не единственный routing key.

### Repository-Local Catalog

Принятый каталог продукта хранится в `docs/spec/_capabilities.yaml`.

```yaml
schema_version: 1

domains:
  identity:
    title: Identity
    responsibility: Идентификация пользователей и управление доступом.

capabilities:
  identity.authentication:
    title: Authentication
    type: business
    responsibility: Проверка учётных данных и создание аутентифицированного контекста.
    excludes:
      - Управление сроком жизни активной сессии
      - Авторизация действий
    actors: [anonymous-user, registered-user]
    entities: [credentials, authentication-attempt]
    events: [authentication-succeeded, authentication-failed]
    spec:
      - docs/spec/identity/authentication.md
    depends_on: [policy.security]
    status: active

  identity.session-management:
    title: Session Management
    type: business
    responsibility: Создание, обновление и завершение пользовательских сессий.
    excludes:
      - Проверка прав доступа
    entities: [session, access-token, refresh-token]
    events: [session-created, session-refreshed, session-expired]
    spec:
      - docs/spec/identity/session-management.md
    depends_on: [identity.authentication, policy.security]
    status: active

policies:
  policy.security:
    title: Security
    spec:
      - docs/spec/policies/security.md
    applies_to: [identity.*, payments.*]
```

Минимальные routing-поля capability:

- стабильный ID;
- `responsibility` и `excludes`;
- actors, entities и events;
- пути к spec-модулям;
- dependencies и policies;
- lifecycle status.

Каталог использует controlled open-world model:

> Каталог считается полным относительно текущей принятой спецификации, но не считается полным относительно всех будущих требований.

ИИ создаёт первоначальную карту при bootstrap и предлагает `catalog delta`, если change не соответствует существующим границам. ИИ не изменяет принятую карту неявно во время routing.

Допустимые результаты routing:

```yaml
routing_result: matched
```

```yaml
routing_result: ambiguous
candidates:
  - identity.authentication
  - identity.session-management
```

```yaml
routing_result: capability-gap
proposed_capability:
  id: identity.account-recovery
  responsibility: Восстановление доступа к учётной записи.
```

`ambiguous` требует уточнения границы. `capability-gap` создаёт явный catalog/spec delta и проходит human gate.

### Capability Creation Criteria

Новая capability оправдана, если выполняется несколько условий:

- отдельная наблюдаемая продуктовая ответственность;
- собственные requirements и scenarios;
- собственные invariants или lifecycle;
- возможность относительно независимого изменения и тестирования;
- собственная терминология или data ownership;
- существующая capability иначе становится неоднородной.

Не следует создавать capability для каждого endpoint, класса, таблицы, пользовательского запроса или task.

## Lifecycle Overview

```text
1. Intake                          -> Change package + immutable request
2. Route and Analyze               -> Typed slice-level deltas
3. Specify                         -> Accepted normative state or spec unchanged
4. Decompose                       -> Executable tasks
5. Target                          -> Failing executable target + Red evidence
6. Implement                       -> Code + Green evidence
7. Verify, Converge and Archive    -> Proof that Delta was fully fused
```

### Naming Rationale

Названия верхнего уровня описывают действия процесса, а `Red`/`Green` остаются внутренними техническими состояниями evidence.

| Step | Why this name | Resulting status/evidence |
|---|---|---|
| `Intake` | Шаг не просто сохраняет ввод, а принимает, очищает и нормализует его | `normalized` |
| `Analyze` | Сопоставляет request с системой и вычисляет typed Delta | `analyzed` |
| `Specify` | Фиксирует нормативную проекцию Delta в spec или подтверждает `spec unchanged` | `specified` |
| `Decompose` | Не проектирует решение заново, а раскладывает принятую Delta на atomic tasks | `decomposed` |
| `Target` | Превращает test oracle в executable target и доказывает текущий gap | `target-confirmed`, Red evidence |
| `Implement` | Изменяет code до достижения frozen target | `implemented`, Green evidence |
| `Verify` | Проверяет полный Fuse и convergence всех затронутых layers | `verified` / `converged` |

`Target` предпочтительнее `Targeting`: последнее может означать выбор файлов, deployment target или scope, тогда как scope уже определён Analyze/Decompose. В DeltaFuse `Target` всегда означает исполняемую цель поведения.

### Step 1: Intake

#### Goal

Преобразовать сырой пользовательский ввод в структурированный, но ещё не интерпретированный change request.

#### Context Contract

Reads:

- текущий пользовательский запрос;
- явно переданные файлы `docs/intake/**`;
- формат change request и sanitization rules.

Must not read:

- `docs/spec/**`;
- decisions и active changes/tasks;
- product tests и code.

Writes:

- `docs/changes/<change-id>/change.yaml` с `status: normalized`;
- `docs/changes/<change-id>/request.md`.

```yaml
id: CHG-042
status: normalized
reported_kind: bug
source_refs:
  - docs/intake/session-refresh-report.md
```

```markdown
## Summary

Краткая формализация запроса без технического решения.

## Claims

- CR-001: При истёкшем access token и валидном refresh token пользователь получает HTTP 500.
- CR-002: Пользователь ожидает продолжения сессии без повторного входа.

## Constraints Reported by User

- CR-003: Формат публичного ответа не должен измениться.

## Unknowns

- Неизвестна воспроизводимость на текущей версии.
```

#### Rules and Gate

- различать observation, expectation, constraint и hypothesis;
- не подтверждать заявленный пользователем тип изменения;
- не придумывать acceptance criteria и technical solution;
- присваивать атомарным утверждениям стабильные `CR-*` IDs;
- сохранять ссылку на raw intake;
- после Intake не переписывать существующие claims молча: уточнения добавлять как revision/superseding claims;
- большой request разрешено делить на claims, но не на implementation tasks;
- gate пройден, когда каждое значимое утверждение представлено claim либо явно исключено.

### Step 2: Route and Analyze

#### Goal

Сопоставить claims с принятой spec, определить classification, affected capabilities, policies, required decisions и analytical slices, а затем вычислить одну или несколько typed deltas.

#### Context Contract

Reads:

- `request.md`;
- `docs/spec/_capabilities.yaml`;
- summaries глобальных policies;
- после routing — только выбранные spec-модули и связанные decisions.

Must not read by default:

- всю spec;
- весь code и все tests;
- unrelated changes/tasks.

Runtime/code evidence запрашивается только отдельной диагностической операцией и явно добавляется в context manifest.

#### Pass A: Routing

Первый проход читает request и capability catalog, но не все spec-модули.

```yaml
change: CHG-042
claims:
  CR-001:
    primary_capability: identity.session-management
    related_capabilities: [identity.authentication]
    policies: [policy.security]
    confidence: high
  CR-002:
    primary_capability: identity.session-management
    related_capabilities: []
    policies: [policy.security]
    confidence: high
```

Каждый claim имеет одну owning capability. Related capabilities и policies могут быть множественными.

#### Pass B: Slice Analysis

Claims группируются по связанным capabilities и dependencies. Каждый slice анализируется в отдельном контексте.

```yaml
slice: SLICE-01
change: CHG-042
claims: [CR-001, CR-002, CR-003]
primary_capability: identity.session-management
related_capabilities: [identity.authentication]
policies: [policy.security]
spec_refs:
  - docs/spec/identity/session-management.md#REQ-SESSION-017
  - docs/spec/policies/security.md#REQ-SEC-004
depends_on: []
```

Хороший analytical slice:

- имеет один independently verifiable outcome;
- имеет одну primary capability;
- включает только необходимые dependencies и policies;
- имеет in scope, out of scope и context budget;
- завершается определённой classification и spec refs;
- явно указывает зависимости от других slices.

Если взаимодействие capabilities само является поведением, создаётся отдельный integration slice.

#### Context Overflow Strategy

Риск переполнения реален: объём анализа растёт примерно как число claims, умноженное на число потенциально затронутых spec-модулей.

При превышении budget:

1. Разделить request на атомарные claims без изменения смысла.
2. Выполнить routing только по capability catalog.
3. Сгруппировать claims по connected components capability graph.
4. Разделить крупную группу по независимым outcomes/scenarios.
5. Передать shared invariants и policies каждому дочернему slice.
6. Создать integration slices для межгрупповых контрактов.
7. Выполнить global reconciliation по summaries всех slices.

Нельзя разрывать одно requirement с его invariant, producer/consumer без integration slice, trust boundary без общей policy или migration sequence без dependencies.

#### Outcomes

| Outcome | Meaning | Next step |
|---|---|---|
| `already-specified` | Spec уже требует ожидаемое поведение | Candidate implementation bug или no-op |
| `spec-gap` | Поведение не определено | Spec delta |
| `spec-conflict` | Запрос противоречит spec | Reject или spec delta |
| `decision-required` | Есть существенные варианты | Decision Record и human gate |
| `out-of-scope` | Запрос вне границ | Reject или новый change |
| `capability-gap` | Нет подходящей capability | Catalog delta |
| `not-enough-information` | Нет однозначного результата | Stop-and-Ask |

#### Global Reconciliation

После анализа slices отдельный проход читает только summaries, dependency graph, claim coverage и список решений. Он проверяет:

- каждый `CR-*` покрыт одним owning slice;
- нет конфликтующих изменений requirement;
- междоменные зависимости представлены integration slices;
- blocking decisions имеют terminal status, а accepted decisions отражены в spec, когда это требуется;
- global policies не потеряны;
- порядок работ разрешим.

#### Decision Convergence Loop

Итеративным является именно шаг Route and Analyze:

```text
Analyze affected slices
    -> propose or refine Decision Records
    -> human clarification/acceptance/rejection
    -> re-analyze only affected slices
    -> global reconciliation
    -> repeat if new blocking questions appear
```

Один цикл не обязан повторно читать весь request и всю spec. Он получает изменившиеся decisions, summaries затронутых slices, их exact spec refs и dependency edges.

Условие выхода из цикла:

- у всех blocking questions есть terminal decision status;
- принятые решения отражены в typed deltas;
- global reconciliation не обнаруживает новых blocking questions;
- каждый slice имеет достаточно определённое normative основание для Specify.

Если новый существенный вопрос обнаружен позднее на Specify, Decompose, Target или Implement, downstream-шаг не решает его молча: Change возвращается в Route and Analyze, после чего повторно проходят только затронутые downstream-проекции.

#### Outputs and Gate

Writes:

- `routing.yaml`;
- `analysis.md`;
- `slices/<slice-id>.md`;
- draft Decision Record/catalog delta;
- typed deltas в `change.yaml` и соответствующих slice-файлах;
- начальный `coverage.yaml`.

Gate: все claims классифицированы, blocking questions и decisions закрыты, каждый slice имеет точные spec refs или spec delta, а каждая delta перечисляет затронутые и незатронутые artifact layers.

### Step 3: Specify

#### Goal

Применить specification-проекцию delta и сделать принятую spec нормативно достаточной для планирования и реализации. Если specification operation равна `none`, явно подтвердить неизменность spec.

#### Context Contract

Reads:

- один analyzed slice;
- точные затронутые spec-модули;
- принятые decisions/catalog delta;
- необходимые соседние requirements.

Writes:

- surgical changes в `docs/spec/**`;
- capability catalog при принятом catalog delta;
- ненормативный `spec-delta.md` как журнал intent/scope;
- coverage information.

#### Cases

Requirement delta:

```text
Analyzed slice
    -> Proposed spec delta
    -> Surgical spec edit
    -> Spec audit
    -> Human acceptance
    -> Specified
```

Spec delta использует `ADDED`, `MODIFIED`, `REMOVED` и stable requirement IDs. Основная spec остаётся живым описанием поведения, без change log внутри требований.

Implementation bug:

```yaml
intent: bugfix
delta_kind: conformance
requirement_delta: none
spec_refs:
  - docs/spec/identity/session-management.md#REQ-SESSION-017
```

Spec не изменяется; существующие requirement references являются нормативным основанием.

Refactor/maintenance: при неизменном observable behavior spec не изменяется, а change перечисляет сохраняемые invariants.

Gate:

- spec delta принят и находится в основной spec; либо
- `requirement_delta: none` подтверждён существующими requirements;
- accepted decisions, влияющие на нормативное поведение, зеркалированы в spec;
- change не содержит нормативного поведения вне `docs/spec/**`.

### Step 4: Decompose

#### Goal

Преобразовать одну принятую slice-level delta в dependency-ordered набор atomic tasks. Планирование является первой исполнимой частью Fuse, но не изменяет product code.

#### Context Contract

Reads:

- один analyzed slice;
- принятые spec refs;
- optional `design.md`;
- capability dependency map;
- компактный code/test index или точечные файлы, если без них нельзя определить executable boundary;
- существующие task IDs/dependencies.

Must not read by default: весь raw intake, всю spec/codebase и unrelated tasks.

#### Task Slicing Rules

Task должна:

- давать один проверяемый результат;
- помещаться в одну implementation session;
- иметь exact spec/slice refs и test oracle;
- перечислять allowed/forbidden paths или symbols, если известно;
- иметь явные dependencies;
- завершаться зелёным состоянием;
- не копировать нормативный текст spec;
- не содержать скрытого architectural decision.

Предполагаемые строки кода не являются главным критерием. Важнее outcome, связность поведения, количество файлов и context budget.

#### Task Contract

```yaml
id: TASK-104
change: CHG-042
slice: SLICE-01
kind: bugfix
status: pending
depends_on: []
requirement_delta: none
spec_refs:
  - docs/spec/identity/session-management.md#REQ-SESSION-017
  - docs/spec/policies/security.md#REQ-SEC-004
design_ref: none
allowed_paths: [src/session/**, tests/session/**]
forbidden_paths: [src/auth/credentials/**]
```

```markdown
## Outcome

Валидный refresh token обновляет истёкшую сессию без HTTP 500.

## Test Oracle

- GIVEN access token истёк, refresh token валиден.
- WHEN клиент вызывает refresh.
- THEN возвращается новая сессия по REQ-SESSION-017.

## Unchanged Behavior

- Активная сессия не проходит лишний refresh.
- Публичный формат ответа не изменяется.

## Verification

- Targeted command: `<command>`
- Regression command: `<command>`
```

Implementation bug декомпозируется из observed behavior, existing spec refs, reproduction/test oracle, unchanged behavior и scope constraints. Spec delta для создания tasks не требуется.

Writes: `tasks/TASK-*.md`, task metadata в `change.yaml`, active change index и `slice -> task` coverage.

Gate: требования slice покрыты задачами, каждая задача имеет test oracle, dependencies разрешимы, spec и blocking decisions приняты, scope не расширен.

### Step 5: Target

#### Goal

Применить test-проекцию delta: создать исполняемый тест, доказывающий отсутствие требуемого поведения или наличие дефекта до изменения production code.

#### Context Contract

Reads:

- одну task;
- exact spec refs;
- reproduction и unchanged behavior;
- релевантные test conventions, fixtures/helpers;
- минимальные public interfaces product code.

Must not read by default: весь request, spec, codebase и unrelated tests.

#### Rules

- test пишется по task и spec refs, не непосредственно по raw request;
- production code не изменяется;
- test должен падать по ожидаемой причине;
- compile error, missing fixture, environment failure и случайный timeout не являются подтверждённым Red;
- test проверяет observable behavior на минимально достаточном уровне;
- flaky Red не считается evidence;
- test не кодирует поведение вне task/spec.

#### Red Evidence

```yaml
task: TASK-104
test: AuthRefreshTest.expiredTokenWithValidRefresh
command: ./gradlew test --tests AuthRefreshTest.expiredTokenWithValidRefresh
result: failed
failure_kind: assertion
expected_failure:
  expected: HTTP 200 with refreshed session
  actual: HTTP 500
captured_at: YYYY-MM-DDTHH:MM:SSZ
```

Evidence не содержит секретов, токенов, полных production payload и credential-bearing URL.

Если test сразу Green, production fix запрещён. Возможные outcomes: `not-reproduced`, `already-fixed`, `wrong-test-level`, `invalid-test-oracle`, `environment-specific`, `flaky-report`. Change возвращается в Analyze/Decompose; нельзя искусственно ломать assertion.

Если Red и Green выполняются разными сессиями, test diff и evidence должны быть доступны следующей. Они могут оставаться в task branch/worktree или в локальном промежуточном commit, который запрещено отдельно merge/push. В итоговом PR красного состояния быть не должно.

Gate: test создан, упал на исходной реализации по ожидаемой причине, evidence записан, production code не изменён.

### Step 6: Implement

#### Goal

Применить implementation-проекцию delta: минимально изменить production code так, чтобы подтверждённый Red стал Green без нарушения связанных требований.

#### Context Contract

Reads:

- одну task;
- exact spec refs;
- frozen Red test/evidence;
- релевантный product code;
- optional design;
- соседние tests для regression verification.

#### Rules

- source of behavior — spec;
- source of operational scope — task;
- Red test frozen: его нельзя удалить, ослабить или переписать ради Green;
- ошибочный test возвращается на Target/Decompose;
- change ограничивается allowed scope;
- scope expansion фиксируется как deviation и переоценивается;
- сначала targeted test, затем regression suite capability;
- targeted Green без regression checks не закрывает task;
- Implementer не изменяет spec или decisions.

#### Green Evidence

```yaml
task: TASK-104
targeted_test:
  command: ./gradlew test --tests AuthRefreshTest.expiredTokenWithValidRefresh
  result: passed
regression_suite:
  command: ./gradlew test --tests "*Session*"
  result: passed
changed_paths:
  - src/session/SessionRefreshService.java
  - tests/session/AuthRefreshTest.java
deviations: []
```

Gate: Red стал Green без ослабления, regression suite прошёл, scope соблюдён, evidence безопасен.

### Step 7: Verify, Converge and Archive

#### Goal

Доказать, что все проекции delta применены ко всем объявленным слоям, change сошёлся в согласованное состояние, а завершённая работа может быть удалена из активного контекста без потери provenance.

#### Context Contract

Reads: change/slice summaries, coverage, task states, exact spec refs, test evidence, code/spec diff и decision statuses. Углубление выполняется только по найденному разрыву.

#### Traceability

```text
Raw source
    -> CR claim
        -> Change analysis
            -> Slice-level Delta
                -> Requirement/spec ref
                    -> Task
                        -> Test
                            -> Implementation evidence
```

| Claim | Slice / Delta | Requirement | Task | Test | Result |
|---|---|---|---|---|---|
| CR-001 | SLICE-01 / DELTA-01 | REQ-SESSION-017 | TASK-104 | AuthRefreshTest | green |
| CR-002 | SLICE-01 / DELTA-01 | REQ-SEC-004 | TASK-104 | AuthRefreshTest | green |

#### Outcomes

| Outcome | Meaning |
|---|---|
| `converged` | Delta полностью fused; claims, spec, tasks, tests и code согласованы |
| `tasks-missing` | Для требования отсутствует реализация/проверка |
| `spec-gap` | Реализация потребовала неописанного поведения |
| `test-gap` | Нет достаточного executable evidence |
| `scope-drift` | Изменения вышли за scope |
| `decision-gap` | Есть непринятое архитектурное решение |
| `not-reproduced` | Заявленный bug не подтверждён |

Verify не исправляет code молча: разрыв возвращает change владельцу соответствующего upstream-артефакта или добавляет новую задачу.

После `converged`:

1. Подтвердить terminal status всех tasks и сохранить их history/evidence.
2. Удалить Change из active index и при необходимости обновить `CHANGELOG.md`.
3. Переместить весь change package в `docs/archive/changes/<date>-<change-id>/`.
4. Сохранить `change.yaml`, request, analysis, slices/deltas, design, task history и evidence.
5. Не включать archive в default implementation context.

Archive сохраняет auditability, но не расходует контекст локальной LLM.

## Bug Workflow

### Implementation Bug

Spec однозначно описывает правильное поведение, а наблюдение ему противоречит.

```text
Bug intake
    -> Request
    -> Analysis against existing spec
    -> Conformance delta
    -> requirement_delta: none
    -> Decompose from spec refs + reproduction
    -> Red regression test
    -> Green fix
    -> Verify
```

До Red это только `candidate implementation bug`. Подтверждённым он становится после воспроизводимого падения или эквивалентного надёжного runtime evidence.

### Specification Bug

Spec молчит, противоречит сама себе или задаёт неправильное ожидаемое поведение.

```text
Bug intake
    -> Request
    -> Analysis
    -> Requirements delta
    -> Spec delta or Decision Record
    -> Human acceptance
    -> Decompose
    -> Target
    -> Implement
    -> Verify
```

### Not a Bug

Наблюдаемое поведение соответствует принятой spec. Запрос отклоняется либо переклассифицируется в feature/spec change.

### Bug Analysis Contract

Bug slice содержит:

- current/observed behavior;
- expected behavior с authoritative spec refs;
- unchanged behavior;
- reproduction и environment/version;
- scope constraints и risk;
- suspected area как гипотезу;
- test oracle;
- критерии `verified`, `partial`, `failed`, `not-reproduced`.

Главный invariant:

> Production fix нельзя начинать, пока нет детерминированного Red, падающего по ожидаемой причине.

Tasks можно сформировать до executable Red, если каждая task содержит проверяемый test oracle. Red является первым implementation action.

## Bootstrap and Change Profiles

Bootstrap и change — разные entry points с общим хвостом, а не независимые реализации фреймворка.

### Bootstrap

Применяется только при отсутствии принятого baseline specification pack.

```text
Raw initial requirements
    -> Normalize claims
    -> Discover candidate domains/capabilities
    -> Human review of boundaries
    -> Create capability catalog
    -> Create baseline spec modules
    -> Resolve decisions
    -> Audit and accept baseline
    -> Decompose slices into tasks
    -> Target/Implement
    -> Verify
```

При discovery ИИ выделяет actors, outcomes, entities/ownership, events, invariants, external systems, trust boundaries, policies и candidate capabilities. Человек принимает границы; затем catalog изменяется только явными deltas.

### Change

```text
Raw change
    -> Intake
    -> Route and Analyze
    -> Typed Delta
    -> Optional decision/spec/catalog update
    -> Fuse through Decompose, Target and Implement
    -> Verify Convergence and Archive
```

Создание нового сервиса внутри репозитория с принятой spec — крупный change, а не повторный bootstrap всего репозитория. Он создаёт capabilities, spec, design, decisions и implementation slices.

Глобальный state нужен только для baseline gate:

```yaml
baseline: draft | accepted
```

Текущая работа отслеживается per change:

```text
normalized
    -> analyzing
    -> blocked-on-decision
    -> analyzed
    -> specification-proposed
    -> specified
    -> decomposed
    -> target-confirmed
    -> implementing
    -> implemented
    -> verified
    -> archived
```

Terminal states: `rejected`, `duplicate`, `not-reproduced`, `superseded`. Большой change хранит status каждого slice.

## Skill Context Contracts

Каждый skill декларативно описывает контекст:

```yaml
context:
  reads:
    required: []
    optional: []
  writes: []
  must_not_read: []
  must_not_write: []
  budget:
    max_tokens: <repository-configured>
    max_files: <repository-configured>
  escalation:
    on_missing_context: stop-and-ask
    on_budget_exceeded: split-slice
```

| Step | Required context | Primary output |
|---|---|---|
| Intake | Raw intake | `change.yaml` + `request.md` |
| Route/Analyze | Change root + request + catalog + relevant spec | Routing, analysis, typed deltas, slices, decisions |
| Specify | One slice + exact spec + accepted decisions | Accepted spec or `delta: none` |
| Decompose | One accepted delta + spec + optional design/index | Atomic tasks |
| Target | One task + spec refs + test context + public interfaces | Failing test + Red evidence |
| Implement | One task + spec refs + frozen target + relevant code | Code + Green evidence |
| Verify | Coverage + summaries + evidence + diffs | Verification and archive |

Контекст передаётся точными путями, requirement IDs, anchors и symbols. Свободный summary не заменяет authoritative reference.

## Requirement and Scenario Identity

Для устойчивой трассировки requirements/scenarios имеют stable IDs, а не только изменяемые Markdown anchors.

```markdown
### REQ-SESSION-017: Refresh expired session

Система MUST обновить сессию при валидном refresh token.

#### SC-SESSION-017-A: Expired access token

- GIVEN access token истёк
- AND refresh token валиден
- WHEN клиент обновляет сессию
- THEN система возвращает новую сессию
```

```yaml
spec_refs:
  - path: docs/spec/identity/session-management.md
    requirement: REQ-SESSION-017
    scenarios: [SC-SESSION-017-A]
```

## Design Artifact Rules

`design.md` создаётся, если есть хотя бы один фактор:

- несколько capabilities/services;
- новый architectural pattern или external dependency;
- значимое изменение data model;
- migration/rollback complexity;
- security/trust-boundary impact;
- performance/concurrency complexity;
- несколько реализаций одинаково соответствуют spec.

Design описывает approach, risks, migration и boundaries. Он не копирует requirements и не заменяет Decision Record для долговременного выбора.

## Human Gates

| Gate | Human responsibility |
|---|---|
| Capability boundary | Принять initial map или catalog delta |
| Decision | Принять/отклонить product, architecture, integration, policy или operational решение |
| Specification | Принять baseline или normative change |
| Scope expansion | Разрешить существенное расширение change/task |
| Final integration | Review и merge результата |

Оркестратор может провести несколько логических шагов одной командой, но границы артефактов, статусы и review gates сохраняются.

## Orchestration and Skill Granularity

Логические шаги не обязаны один к одному соответствовать пользовательским командам.

Простые entry points:

```text
/bootstrap
/change
/fix-bug
```

Specialized primitives:

```text
/intake
/analyze-change
/specify-change
/decompose-change
/target-task
/implement-task
/verify-change
```

Для маленького change `/change --quick` может последовательно выполнить несколько primitives. Каждый primitive всё равно создаёт артефакт и проходит gate: уменьшается церемония, но не смешиваются роли и источники истины.

## Core Invariants

1. Product behavior реализуется только по принятой `docs/spec/**`.
2. Канонический process, skill contracts, schemas и validators живут только в DeltaFuse framework repository.
3. Product repository не содержит редактируемую копию `docs/**`; он подключает и pin-ит framework через `.deltafuse/config.yaml` и `.deltafuse/lock.yaml`.
4. Каждый Change фиксирует framework/schema version, на которой он был создан или к которой был явно мигрирован.
5. Repo-local agent adapters являются проверяемыми generated artifacts и не становятся вторым process source.
6. Raw intake и change request не являются requirements.
7. Change является контейнером lifecycle; request является входом; delta является результатом анализа.
8. Каждый change имеет `change.yaml`, request и analysis.
9. Каждый ready slice имеет typed delta, перечисляющую затронутые artifact layers.
10. Spec delta опционален; analyzed change и typed delta обязательны.
11. `docs/decisions/**` может хранить product, architecture, integration, policy и operational decisions; непринятый вопрос не является требованием.
12. Accepted decision, меняющий observable behavior, contract, policy или invariant, отражается в spec до реализации.
13. Implementation bug имеет `delta_kind: conformance`, `requirement_delta: none` и exact `spec_refs`.
14. Fuse изменяет только layers, объявленные в delta, и проверяет invariants незатронутых layers.
15. Tasks являются дочерними артефактами Change; глобального lifecycle-каталога `docs/todo/**` нет.
16. Implementer не изменяет spec или decisions.
17. Decomposer не придумывает непринятое поведение.
18. Production fix не начинается без подтверждённого Red.
19. Green-agent не ослабляет и не удаляет Red test.
20. Targeted Green дополняется regression verification.
21. Каждый claim трассируется через delta до requirement, task, test и result.
22. Каждый claim имеет одну owning capability.
23. Cross-cutting policies загружаются по routing rules, а не по памяти агента.
24. Новый domain/capability появляется только через catalog delta.
25. При превышении context budget работа режется на slices, а не выполняется с обрезанным контекстом.
26. Global reconciliation обязателен после анализа нескольких slices.
27. Route and Analyze повторяется до decision convergence; новый поздний blocking question возвращает Change в этот шаг.
28. Завершённые change artifacts архивируются, а не уничтожаются.
29. Archive не входит в default implementation context.
30. Diffs являются evidence, но не источником requirements.
31. Ошибка upstream-артефакта возвращается его владельцу и не исправляется молча downstream-агентом.

## Migration from Current DeltaFuse

Рекомендуемый порядок внедрения:

1. Инвентаризировать текущие файлы и разделить framework-owned process artifacts и product-owned state.
2. Сделать `delta-fuse/docs/**`, `skills/**`, schemas, validators, templates и migrations единственным каноническим framework package.
3. Добавить installer/resolver для `.deltafuse/config.yaml` и `.deltafuse/lock.yaml`, включая version/hash validation и controlled upgrade.
4. Оставить в product `AGENTS.md` только тонкий repository adapter; локальные tool-specific skills генерировать с version/hash metadata.
5. Заменить product scaffold на `docs/intake/`, `docs/changes/`, `docs/spec/`, `docs/decisions/` и `docs/archive/`; не копировать туда `docs/`.
6. Удалить runtime-смысл `docs/init/`: baseline хранить в config, исходные bootstrap-материалы переносить в intake/archive.
7. Перенести элементы `docs/todo/` в `docs/changes/<change-id>/tasks/`; для legacy task без Change создать migration Change и сохранить provenance.
8. Расширить существующий `docs/decisions/` общей Decision schema с `kind`, `status`, owner, affected capabilities и spec refs.
9. Добавить `docs/changes/`, обязательный `change.yaml` и шаблоны request/analysis.
10. Зафиксировать терминологию `Request -> Analyze -> Delta -> Fuse -> Converge` во всех process-инструкциях.
11. Изменить `/triage`: создавать Change package и immutable request, но не atomic tasks; затем переименовать entry point в `/intake`.
12. Добавить typed slice-level delta model и layer projections, используя projection `tasks`, а не `todo`.
13. Добавить capability catalog и bootstrap-процедуру его построения.
14. Расширить spec audit routing/catalog validation и claim/delta coverage.
15. Добавить decision convergence loop в Route and Analyze и возврат в него при позднем blocking question.
16. Заменить `/plan-story` универсальным `/decompose-change`, принимающим analyzed delta, а не только spec/diff.
17. Вынести изменение spec из `/implement-task`; spec принимается до Decompose.
18. Разделить TDD на явные Target/Implement stages с внутренними Red/Green gates, даже если сначала их выполняет один skill.
19. Добавить Red/Green evidence.
20. Добавить `/verify-change` с cross-artifact convergence и проверкой полного Fuse.
21. Архивировать Change package целиком вместо безвозвратного удаления task history.
22. Убрать ссылки на отсутствующие skills и старые `init`/`todo` paths.
23. Заменить `trivial` независимыми classification axes.
24. Добавить stable requirement/scenario IDs и link validation.
25. После стабилизации primitives добавить `/bootstrap`, `/change`, `/fix-bug` orchestrators.

## Definition of Done for the Process Redesign

- [ ] Каждый Change имеет компактный управляющий `change.yaml` и immutable request.
- [ ] Канонические process files существуют только в DeltaFuse framework repository и не копируются в product repository.
- [ ] Product pin-ит framework version/hash, а каждый активный Change фиксирует использованную process/schema version.
- [ ] Generated agent adapters проверяются против lock-файла и не редактируются как process source.
- [ ] Product layout использует `intake/`, `changes/`, `spec/`, `decisions/`, `archive/` без runtime-папок `init/`, `todo/` и локальной `process/`.
- [ ] Raw request проходит Intake -> Archive без чтения чата downstream-стадиями.
- [ ] Analyze преобразует claims в typed slice-level deltas; request не используется как готовая delta.
- [ ] Route and Analyze сходится только после закрытия blocking decisions и отсутствия новых вопросов на global reconciliation.
- [ ] `decisions/` поддерживает product, architecture, integration, policy и operational kinds; accepted normative effects отражаются в spec.
- [ ] Implementation bug создаёт tasks при `requirement_delta: none` из analysis, spec refs и reproduction.
- [ ] Feature/spec bug не планируется до принятия spec change.
- [ ] Tasks находятся внутри owning Change и архивируются вместе с ним.
- [ ] Большой change делится на capability slices с global reconciliation.
- [ ] Каждый skill имеет declarative context contract.
- [ ] Ни один skill не загружает всю spec/codebase по умолчанию.
- [ ] Red подтверждён ожидаемой причиной и evidence.
- [ ] Green нельзя получить изменением test oracle без возврата upstream.
- [ ] Coverage проходит цепочку `CR -> analysis -> delta -> requirement -> task -> test -> result`.
- [ ] Fuse изменяет все объявленные delta layers, не затрагивает остальные и завершается convergence proof.
- [ ] Capability catalog расширяется только через delta и human gate.
- [ ] Bootstrap и change используют общие primitives.
- [ ] Завершённые changes исчезают из active context, но сохраняются в archive.

## Reference Influences

Модель сочетает практики:

- OpenSpec: change package, optional spec delta, conditional design, tasks и archive;
- GitHub Spec Kit: spec/plan/tasks, cross-artifact analysis и convergence;
- Spec Kit Bug Extension: assess/fix/test для bugs;
- Kiro Bugfix Specs: current, expected, unchanged behavior и regression prevention;
- BDD/TDD: concrete examples, executable specification и Red до implementation.

Первичные источники:

- https://openspec.dev/docs/schemas/spec-driven
- https://openspec.dev/docs/quickstart
- https://github.com/github/spec-kit/blob/main/docs/reference/agentic-sdd.md
- https://github.com/github/spec-kit/blob/main/docs/reference/agentic-bugfix.md
- https://kiro.dev/docs/specs/bugfix-specs/
- https://cucumber.io/docs/bdd/
