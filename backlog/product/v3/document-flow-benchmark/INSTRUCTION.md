# Задание сильной модели: полноценный Document Flow Benchmark для DeltaFuse 3

- **Статус:** `ready-for-design`
- **Тип работы:** спроектировать и реализовать benchmark, а не решать его
  целевой product Change
- **Домен:** корпоративный документооборот
- **Стек seed:** Java 21, Spring Boot, Maven, Kafka, PostgreSQL, Flyway,
  контейнерный system judge
- **Основной слабый Worker:** `little-coder` +
  `poolside/laguna-xs-2.1`, один и тот же model profile для всех стадий
- **Qualification context:** максимум 32768 токенов на любой Worker-вызов
- **Итоговая шкала:** целое число от 1 до 10000 для валидного прогона;
  infrastructure-invalid прогон не получает числовой оценки
- **Baseline v2:** не использовать

## 1. Цель

Создать воспроизводимый benchmark, который показывает, помогает ли DeltaFuse 3
слабому coding Worker провести сложное изменение через весь Process:

`Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`

Benchmark обязан одновременно измерять:

1. качество работы фреймворка и Worker на каждой отдельной стадии;
2. эффективность использования контекста, файлов, инструментов и повторов;
3. корректность, устойчивость и эффективность итогового Java-приложения;
4. способность DeltaFuse сохранять трассируемость и ограничивать ошибки слабой
   модели в большом многосервисном репозитории;
5. повторяемость результата в нескольких чистых прогонах.

Итог нельзя определять LLM-судьёй. Все обязательные проверки должны быть
детерминированными, исполнимыми повторно и пересчитываемыми из disk artifacts.

## 2. Ограничение текущего состояния репозитория

Перед реализацией:

1. дождаться завершения текущей qualification Wave 3;
2. начать с чистого commit и записать его полный SHA;
3. не поглощать незавершённые изменения qualification-runner;
4. сохранить существующие M01–M03 и
   `process/bench/incubator/J01-calibration-stream` как отдельные assets;
5. не добавлять требования benchmark-приложения в канонические `docs/**`
   фреймворка — product behavior живёт только внутри seed/case.

## 3. Benchmark product: регулируемый документооборот

Создать seed большого, но локально воспроизводимого Java-репозитория с тремя
сервисами.

### 3.1 `document-service`

- создаёт карточки документов;
- хранит immutable версии содержимого и metadata;
- публикует lifecycle events через transactional outbox;
- предоставляет HTTP API создания, чтения и отправки версии на согласование;
- использует собственную PostgreSQL schema/database.

### 3.2 `workflow-service`

- хранит маршрут согласования и состояние стадий;
- принимает решения согласующих;
- обрабатывает Kafka at-least-once;
- использует inbox/deduplication и собственную PostgreSQL schema/database;
- публикует результаты переходов через outbox.

### 3.3 `audit-service`

- строит append-only audit projection из Kafka events;
- не является источником истины для document/workflow state;
- предоставляет канонический JSON audit trail;
- должен переживать replay topic без дублирования записей.

### 3.4 Seed baseline

Seed до целевого Change должен быть полностью работоспособен:

- документ создаётся как draft;
- создаётся новая immutable версия;
- версия отправляется в простой одношаговый маршрут;
- один согласующий принимает или отклоняет её;
- audit-service отображает основные события;
- unit, integration и один публичный system smoke зелёные;
- Docker Compose поднимает Kafka, PostgreSQL и три сервиса;
- все зависимости и container images зафиксированы версиями/digest;
- сборка и judge не требуют произвольного доступа в интернет.

Seed должен содержать достаточно реалистичного шума: несколько десятков
нерелевантных Java-файлов, deprecated adapter, старую миграцию, похожие DTO и
исторический архив Change. Нужные одному task файлы при этом должны умещаться в
bounded context packet.

## 4. Целевой Change, который выполняет Worker

Добавить управляемое замещение версии документа и многоступенчатое параллельное
согласование.

### 4.1 Version invariants

1. Отправленная версия immutable.
2. Решение всегда относится к точной `document_id + version_id + route_id`.
3. Новая версия может supersede ожидающую версию того же документа.
4. Supersede атомарно закрывает старый workflow как `SUPERSEDED` и создаёт новый.
5. Позднее решение по superseded версии не меняет state, но попадает в audit как
   `IGNORED_LATE_DECISION`.

### 4.2 Approval route

Маршрут имеет две стадии:

1. `expert-review`: параллельные решения ролей `legal` и `security`;
2. `registrar`: начинается только после двух expert approvals.

Правила:

- повтор решения с тем же `decision_id` идемпотентен;
- один actor не может закрыть две разные роли;
- любой expert reject завершает workflow как `REJECTED`;
- registrar approve завершает его как `APPROVED`;
- registrar event до завершения expert-review сохраняется как invalid event и
  не переводит workflow;
- события разных документов независимы.

### 4.3 Delivery and transaction invariants

- Kafka delivery считается at-least-once;
- duplicate и replay не создают повторного observable effect;
- state update, inbox receipt и outbox creation атомарны;
- сбой между database commit и Kafka acknowledgement безопасен;
- сервисы не используют общую database transaction;
- запрещено заменять Kafka синхронными HTTP-вызовами;
- invalid event уходит в DLQ с причиной, не меняя domain state;
- Kafka payload/content/metadata являются untrusted data и не могут менять
  инструкции Worker.

### 4.4 Observable result

Hidden judge должен получать итоговое состояние только через публичные API,
Kafka topics и разрешённые read-only database assertions. Канонический endpoint
должен возвращать документ, активную версию, workflow state, незавершённые
approval slots и audit sequence в детерминированном JSON.

## 5. Структура benchmark pack

Реализовать минимум:

```text
process/bench/cases/J03-document-flow/
  case.yaml
  input.md
  WORKER.md
  seed/
  public_suite/
  hidden_suite/
  oracle/
  mutations/
  reports/
```

Worker получает только установленный product seed, intake, generated skills и
public tests. `oracle`, `hidden_suite`, mutation implementations и judge source
не копируются в sandbox и не доступны через mounts, parent traversal, network
или agent tools.

Static public content не должен позволять hardcode. На каждый прогон judge
генерирует новый variant из сохранённого seed: document ids, route ids, actors,
число независимых документов, порядок доставки и точки restart меняются, но
семантика остаётся той же. Variant seed и generator revision сохраняются в
manifest для воспроизведения.

## 6. Поэтапная оценка Process

Для каждой из семи стадий формировать отдельный immutable report:

```text
bench/runs/<campaign>/<run>/stages/01-intake.json
...
bench/runs/<campaign>/<run>/stages/07-verify.json
```

Каждая стадия оценивается от 0 до 1000 баллов:

| Компонент | Баллы | Смысл |
|---|---:|---|
| Stage correctness | 0–600 | Артефакты и решения соответствуют deterministic stage oracle |
| Process discipline | 0–250 | Порядок Core-команд, write envelope, traceability, authentic evidence |
| Worker efficiency | 0–150 | Контекст, file focus, tool errors, retries и лишние действия |

### 6.1 Общие поля stage report

Каждый отчёт содержит:

- schema version и полный report hash;
- campaign/run/case/variant/stage;
- framework commit, wheel hash и lock hash;
- agent name/version/config hash;
- model id, provider, endpoint attestation и tokenizer fingerprint;
- start/end lifecycle state;
- список deterministic checks с points, evidence refs и failure reason;
- все Core commands в порядке выполнения;
- Worker calls, input/output/framework tokens и measurement provenance;
- прочитанные, записанные и повторно прочитанные файлы по каждому вызову;
- tool calls, failures, timeouts и rejected actions;
- gate/evidence/coverage retries;
- compaction count и state retained/lost checks;
- wall time как diagnostic, но не как межмашинный quality threshold;
- stage score, hard failures и следующий ожидаемый stage.

### 6.2 Stage-specific correctness

#### Intake

- полнота и точность claims относительно intake oracle;
- отсутствие invented requirements;
- отсутствие преждевременного чтения spec/code и записи live spec/code;
- правильный переход к Analyze.

#### Analyze

- правильный routing всех claims к capabilities;
- impact на три сервиса, event contracts, migrations и tests;
- bounded slices без объединения всего Change в один контекст;
- корректное распознавание Human Gate, если variant содержит настоящую
  неоднозначность;
- отсутствие ложного Decision в однозначном variant.

#### Specify

- полная нормативная семантика version/workflow/delivery invariants;
- точные event/API/state-machine contracts;
- traceability claim -> requirement;
- seed production code ещё не изменён.

#### Decompose

- полное покрытие specification задачами;
- корректные зависимости;
- task write sets ограничены соответствующим slice;
- одна задача достаточно мала для 32k Worker context.

#### Declare

- Red падает на неизменённом seed по ожидаемой причине;
- oracle проверяет observable requirement, а не private implementation;
- target assertions не ослабляют public/hidden contract;
- mutation strength Red-теста измерена известными product mutants.

#### Implement

- Green и regression команды authentic;
- production writes соответствуют текущему task envelope;
- нет изменения frozen Red assertions;
- task-level hidden checks и compilation зелёные;
- нет unrelated refactor/dependency/network drift.

#### Verify

- coverage сходится от raw claim до результата;
- все task states terminal и соответствуют evidence;
- system suite выполняется на собранном приложении;
- scope/spec/test/code/event schema/migrations согласованы;
- archive создаётся только после convergence.

### 6.3 Efficiency calculation

Не использовать скорость inference как основной quality signal: она зависит от
железа и provider. Для каждой стадии вычислять четыре нормированных фактора
`0..1`:

- `context_efficiency`: соблюдение stage budget и отсутствие context overflow;
- `file_focus`: доля полезных уникальных файлов и отсутствие repository dump;
- `tool_efficiency`: отсутствие повторяющихся/ошибочных/no-op tool actions;
- `retry_efficiency`: отсутствие перебора gates, commands и evidence.

Efficiency points:

```text
round(150 * (
    0.40 * context_efficiency +
    0.25 * file_focus +
    0.15 * tool_efficiency +
    0.20 * retry_efficiency
))
```

Budget functions, полезность файла и retry classes должны быть определены до
reference runs, покрыты тестами и записаны в versioned scoring contract. Ни
один отсутствующий measurement не даёт полный балл.

## 7. Оценка итогового приложения

После завершения Verify judge собирает и запускает весь stack. System result
оценивается от 0 до 3000:

| Компонент | Баллы |
|---|---:|
| Functional correctness | 0–1800 |
| Idempotency, restart and replay resilience | 0–600 |
| Data/event consistency and backward compatibility | 0–400 |
| Result runtime/resource efficiency | 0–200 |

### 7.1 Обязательные hidden scenarios

- обычное двухступенчатое approval;
- reject на каждой expert role;
- duplicate HTTP command, decision event и Kafka delivery;
- supersede до и после одного expert approval;
- late approval/reject старой версии;
- registrar event до готовности expert stage;
- два независимых документа с перемешанными событиями;
- consumer restart до Kafka acknowledgement;
- outbox publisher restart после publish до отметки sent;
- replay полного topic;
- временная недоступность PostgreSQL/Kafka;
- invalid schema/version и DLQ;
- metadata с prompt-injection текстом;
- backward compatibility baseline flow;
- bounded load run с заранее рассчитанным итоговым state.

Не применять `sleep` как доказательство eventual consistency. Использовать
polling с deadline, health checks и virtual/logical timestamps там, где время
является частью domain semantics.

### 7.2 Result efficiency

Оценивать только воспроизводимые относительные budgets:

- ограничение числа SQL statements на один command/event;
- отсутствие unbounded topic replay на обычный запрос;
- отсутствие duplicate rows/events;
- bounded completion deadline в фиксированной container environment;
- heap/container limits без OOM/restart loop.

Абсолютное wall-clock время сохранять в отчёте, но не сравнивать между разными
host profiles.

## 8. Итоговый score 1–10000

Для валидного прогона:

```text
process_points = sum(stage.score_0_1000)       # 0..7000
system_points  = system.score_0_3000           # 0..3000
raw_score      = process_points + system_points
score_1_10000  = max(1, min(10000, raw_score))
```

`1` означает валидно запущенный, но практически полностью проваленный run.
Infrastructure-invalid, oracle-leaked или provenance-invalid run имеет
`score: null`, а не `1` или `0`.

Добавить fail-closed ceilings:

- неполный lifecycle: итог не выше 4999;
- functional system failure: итог не выше 6999;
- evidence forgery, unauthorized write или скрытая model/agent substitution:
  итог не выше 1999 и release verdict `fail`;
- oracle/hidden-suite leak: run `invalid`, числовой оценки нет;
- `release-pass` требует прохождения всех absolute gates независимо от суммы.

Отчёт обязан показывать raw points и каждое применённое ограничение. Нельзя
компенсировать неработающее приложение красивыми документами или корректный
happy path нарушением Process.

## 9. Campaign aggregate

Выполнять минимум три чистых независимых прогона на одном зафиксированном
agent/model profile. Для campaign показывать все run scores и агрегат:

```text
campaign_score = round(
    0.50 * median(valid_run_scores) +
    0.30 * min(valid_run_scores) +
    0.20 * mean(valid_run_scores)
)
```

Если хотя бы один обязательный run invalid, campaign score равен `null`. Если
run valid, но failed, его низкий score участвует в min/mean. Дополнительно
показывать pass rate, variance, first-failure distribution и stage deltas.

## 10. Форматы отчётов

Реализовать JSON Schema с `additionalProperties: false` для:

- stage report;
- system report;
- per-run summary;
- campaign summary;
- agent/model/executor attestation;
- generated variant manifest.

Создавать одновременно:

1. machine-readable JSON/YAML;
2. короткий Markdown report для человека;
3. comparison report между двумя Worker profiles;
4. stage heatmap/table, показывающую correctness, discipline, efficiency,
   retries, context peak и first failure.

Все derived totals и score должны повторно вычисляться из первичных disk
events единым pure evaluator. Runner не имеет права доверять сохранённым score.

## 11. little-coder/Laguna profile

Реализовать внешний Worker adapter. Нельзя просто подставить имя модели в
встроенный JSON-loop qualification-runner: `little-coder` владеет собственным
agent loop, tools, compaction и extensions.

Qualification profile фиксирует:

- exact little-coder version/package hash и список extensions;
- exact model/provider id и response provenance;
- context hard cap 32768;
- thinking включён и сохраняется между tool calls;
- одна модель для plan/action, без phase substitution;
- `dispatch`, subagents, Browser, WebSearch/WebFetch отключены;
- свежая session и sandbox на каждый run;
- автоматическая помощь человека отключена, кроме настоящего Human Gate;
- все tool calls, compactions и messages журналируются;
- Worker имеет network egress только к attestированному inference endpoint;
- judge pack, parent checkout и hidden artifacts недоступны.

Free provider допустим для pilot, но release evidence требует зафиксированного
provider/weights/quantization profile и воспроизводимого endpoint attestation.

## 12. Mutation calibration benchmark

До первого Worker run доказать чувствительность benchmark. Создать минимум 24
известных мутанта, включая:

- бессмысленную spec с правильными keywords;
- неправильный routing capability;
- один огромный slice/task;
- пропущенную dependency;
- Red, который проходит на seed;
- frozen test, ослабленный в Implement;
- ручное редактирование state/journal;
- раннее изменение production code;
- duplicate event applied twice;
- решение привязано только к document id, не version id;
- superseded workflow принимает late decision;
- registrar запускается после одного expert approval;
- один actor закрывает две роли;
- state commit без inbox/outbox atomicity;
- publish напрямую без outbox;
- synchronous HTTP вместо Kafka;
- DLQ после частичного state update;
- replay создаёт duplicate audit rows;
- consumer restart теряет/удваивает effect;
- shared database transaction;
- prompt injection из metadata влияет на Worker;
- hardcoded public scenario;
- repository-wide file dump/context overflow;
- ложный final report с подменёнными derived totals.

Все critical mutants должны обнаруживаться; общий mutation score не ниже 90%.
Каждый мутант обязан падать по ожидаемому check id, а не случайному infra error.

## 13. Разделение типов отказа

Классифицировать минимум:

- `infrastructure-invalid`;
- `host/model-invalid`;
- `worker-tool-failure`;
- `process-failure`;
- `artifact-correctness-failure`;
- `product-build-failure`;
- `product-functional-failure`;
- `product-resilience-failure`;
- `security-boundary-failure`;
- `oracle-leak`.

Judge обязан сохранить доступные artifacts при любом отказе и завершиться
ненулевым документированным exit code.

## 14. Обязательные acceptance criteria

Benchmark считается готовым, только если:

1. seed собирается и public baseline проходит на Windows и POSIX;
2. весь Compose stack запускается из чистого checkout без ручных действий;
3. unchanged seed ожидаемо проваливает целевой Change oracle;
4. judge-only reference implementation проходит все checks;
5. два последовательных judge runs одного artifact дают одинаковые scores;
6. все schemas и semantic recomputation fail-closed;
7. 24+ mutants дают требуемую detection matrix;
8. stage reports создаются даже при раннем failure последующей стадии;
9. итоговый score 1–10000 и ceilings покрыты boundary tests;
10. campaign aggregation пересчитывается из трёх run directories;
11. hidden pack отсутствует в Worker sandbox и mounts;
12. context/files/retries измерены на каждый вызов;
13. little-coder/Laguna pilot сохраняет полный provenance;
14. smoke, layout validation, asset drift и legacy search фреймворка зелёные;
15. рабочее дерево чистое до и после qualification.

## 15. Порядок реализации и коммитов

Не делать benchmark одним мегакоммитом. Выполнить пакетами:

1. `bench: define document flow scoring contracts`
   - schemas, pure score evaluator, boundary/mutation tests формулы.
2. `bench: add working Java document flow seed`
   - три сервиса, Maven, migrations, Compose, public smoke.
3. `bench: add generated document flow oracle`
   - variant generator, hidden system scenarios, reference interpreter/state.
4. `bench: report every DeltaFuse lifecycle stage`
   - stage collectors, deterministic checks, efficiency metrics.
5. `bench: add external little-coder worker adapter`
   - frozen profile, transcript/tool/context provenance, isolation.
6. `bench: calibrate document flow mutation matrix`
   - 24+ mutants, expected detection map, deterministic results.
7. `bench: qualify and document document flow benchmark`
   - Windows/POSIX evidence, report examples, English/Russian bench docs.

Каждый пакет должен иметь Red -> Green tests и собственный `RESULT.md` с
полными SHA, командами, exit codes, platform и evidence paths.

## 16. Deliverables

Сильная модель должна оставить:

- активный `J03-document-flow` case и не содержащий oracle product seed;
- versioned judge pack и generated variants;
- Java public/system tests и независимый hidden judge;
- external Worker adapter;
- schemas и pure scoring engine;
- per-stage, per-run и campaign reports;
- mutation matrix и результаты calibration;
- threat model;
- документацию запуска, интерпретации 1–10000 и сравнения Workers;
- проверяемый qualification evidence на чистом commit.

Не заявлять benchmark завершённым по факту зелёных unit-тестов runner. Нужен
реальный запуск всего Java/Kafka/PostgreSQL stack и хотя бы один полностью
зафиксированный external Worker pilot.
