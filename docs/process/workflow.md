# Workflow

DeltaFuse преобразует raw intent в bounded Delta, применяет её к затронутым artifact layers и доказывает convergence.

```text
Raw intent
  -> Intake
  -> Route and Analyze
  -> Specify
  -> Decompose
  -> Target
  -> Implement
  -> Verify, Converge and Archive
```

## 1. Intake

Цель: нормализовать raw user input без интерпретации against product.

Шаг читает только user message, явно переданные файлы `docs/intake/**`, artifact templates и sanitization rules. Он не читает product specification, Decisions, tasks, tests или code.

Writes:

- `docs/changes/<change-id>/change.yaml` со `status: normalized` и pinned framework/schema versions;
- immutable `request.md` со stable `CR-*` claim IDs и provenance.

Observation, expectation, constraint и hypothesis разделяются. Intake не подтверждает reported change type, не придумывает acceptance criteria и не выбирает technical solution. Позднее уточнение добавляется как revision или superseding claim, а не молча переписывает историю.

Gate: каждое существенное входное утверждение представлено claim либо явно исключено.

## 2. Route and Analyze

Цель: сопоставить claims с accepted product state и вычислить typed slice-level deltas.

### Routing pass

Прочитать request, `docs/spec/_capabilities.yaml` и compact summaries глобальных policies. Назначить каждому claim одну owning capability, optional related capabilities и policies. Не загружать всю specification или codebase.

### Slice analysis

Сгруппировать связанные claims в bounded analytical slices. Для каждого slice читать только выбранные spec modules, relevant Decisions и явно запрошенный diagnostic evidence. Создать:

- `routing.yaml`;
- `analysis.md`;
- `slices/<slice-id>.md`;
- typed deltas в `change.yaml` и slice artifacts;
- proposed Decision или catalog records при необходимости;
- initial `coverage.yaml`.

Каждая Delta явно проецируется на:

```yaml
specification: none | add | modify | remove | mixed
catalog: none | add | modify | remove
decisions: none | propose | supersede
tasks: none | derive | modify | remove
tests: none | add | modify | remove
implementation: none | add | modify | remove | mixed
evidence: none | record
```

### Analysis outcomes

| Outcome | Meaning |
|---|---|
| `already-specified` | Existing spec уже требует ожидаемое behavior |
| `spec-gap` | Required behavior отсутствует |
| `spec-conflict` | Request противоречит accepted behavior |
| `decision-required` | Существенный выбор требует Decision и human gate |
| `capability-gap` | Routing требует catalog delta |
| `out-of-scope` | Change отклоняется или делится |
| `not-enough-information` | Stop and ask for exact missing information |

### Decision convergence loop

Route and Analyze является итеративным шагом:

```text
analyze affected slices
  -> propose/refine Decisions
  -> human clarification or terminal decision
  -> re-analyze affected slices
  -> global reconciliation
  -> repeat while new blocking questions appear
```

Выход разрешён, только когда все blocking Decisions terminal, accepted choices отражены в typed deltas, global reconciliation не создаёт новых blocking questions, а каждый slice имеет normative basis для Specify.

Если последующий шаг обнаруживает существенный unknown, только затронутые projections возвращаются в Analyze. Downstream-step не принимает решение самостоятельно.

## 3. Specify

Цель: сделать accepted specification достаточной для implementation либо доказать, что она уже достаточна.

Для одного analyzed slice читаются exact spec modules, accepted relevant Decisions, accepted catalog delta и только необходимые соседние requirements.

- Если `requirement_delta` меняет requirements, редактируются только объявленные files/requirements с сохранением stable IDs.
- Если `requirement_delta: none`, spec не меняется, а sufficiency подтверждается exact accepted `spec_refs`.
- Accepted Decision, влияющий на observable behavior, contract, policy или required invariant, зеркалируется в `docs/spec/**`.
- `spec-delta.md` остаётся ненормативным change journal; live specification содержит только текущее imperative behavior.

Gate: spec change принят либо unchanged status доказан; normative behavior не осталось только в Change или Decision.

## 4. Decompose

Цель: преобразовать один specified slice-level Delta в dependency-ordered atomic tasks.

Читаются slice, exact spec refs, optional `design.md`, capability dependency map, compact code/test index либо точечные files и existing task dependencies. Не читаются весь raw intake, вся specification/codebase или unrelated Changes.

Tasks создаются в `docs/changes/<change-id>/tasks/TASK-NNN-<slug>.md`. Каждая task содержит:

- один verifiable outcome и контекст размером с одну implementation session;
- exact Change, slice, requirement и scenario refs;
- test oracle и unchanged behavior;
- dependencies и allowed/forbidden paths или symbols, если известны;
- verification commands;
- отсутствие скопированного normative text и hidden design choice.

Implementation bug декомпозируется из observed behavior, exact existing spec refs, reproduction, oracle, unchanged behavior и scope. Spec delta для его tasks не требуется.

Gate: каждый slice requirement покрыт, dependencies разрешимы, blocking Decisions/specification приняты, scope не расширен.

## 5. Target

Цель: создать executable target, доказывающий gap до изменения production code.

Читаются одна task, exact spec refs, reproduction/unchanged behavior, relevant test conventions/fixtures и только public product interfaces, нужные для oracle. Implementation internals не читаются, если target можно выразить без них.

Rules:

1. Freeze test oracle из task и specification.
2. Добавить или изменить минимальный executable test.
3. Запустить narrow target на неизменённом production code.
4. Потребовать failure по ожидаемой behavioral причине, а не из-за compilation/setup noise.
5. Сохранить sanitized command, exit status, failure category и summary в `evidence/red/`.

Если test уже Green, причина failure неверна или environment ненадёжен, implementation не начинается. Outcome возвращается как `already-satisfied`, `invalid-target`, `environment-blocked` или `not-reproduced`.

## 6. Implement

Цель: сделать frozen target Green минимальным compliant production change.

Читаются одна task, exact spec refs, frozen target, Red evidence, allowed production files/symbols и только required local dependencies.

Implementer не изменяет specification, Decisions, task oracle, expected assertions или unrelated code. Если это необходимо, работа возвращается upstream.

Сначала запускается targeted test, затем scoped regression suite. Commands, exit status, results, changed paths и spec status сохраняются в `evidence/green/`.

Gate: Red стал Green без ослабления target, regressions прошли, scope соблюдён, evidence не содержит secrets.

## 7. Verify, Converge and Archive

Цель: доказать применение каждой объявленной Delta projection и удалить завершённый Change из active context без потери provenance.

Проверяется traceability:

```text
raw source
  -> CR claim
  -> analysis
  -> slice-level Delta
  -> requirement/spec reference
  -> task
  -> test
  -> implementation evidence
```

Читаются compact summaries, coverage, task states, exact refs, evidence, code/spec diffs и Decision statuses. Контекст углубляется только для найденного gap.

Possible results:

- `converged` — все affected layers согласованы;
- `tasks-missing`, `spec-gap`, `test-gap`, `scope-drift` или `decision-gap` — возврат owning upstream step;
- `not-reproduced` — закрытие с evidence вместо недоказанного fix.

После convergence сохраняются terminal task states и evidence, Change удаляется из active index, при необходимости обновляется `CHANGELOG.md`, весь package перемещается в `docs/archive/changes/<date>-<change-id>/`. Archive исключён из default implementation context.

## Bug classification

Входящий bug сначала является claim, а не подтверждённой classification.

### Implementation bug

Accepted spec однозначно задаёт correct behavior, а runtime observation ему противоречит:

```text
Request -> Analyze against spec -> conformance Delta
  -> requirement_delta: none -> Decompose -> Target/Red
  -> Implement/Green -> Verify
```

Bug становится подтверждённым только после reproducible Red или эквивалентного reliable runtime evidence.

### Specification bug

Spec отсутствует, противоречива или нормативно неверна:

```text
Request -> Analyze -> requirements Delta -> optional Decision
  -> human acceptance -> Specify -> Decompose -> Target -> Implement -> Verify
```

### Not a bug

Observed behavior соответствует accepted spec. Change отклоняется или переклассифицируется в feature/specification change.

## Bootstrap profile

Bootstrap применяется только при `.deltafuse/config.yaml` с `project.baseline: draft`:

```text
normalize initial claims
  -> discover candidate domains/capabilities
  -> human review of boundaries
  -> create capability catalog
  -> create baseline spec modules
  -> resolve Decisions
  -> audit and accept baseline
  -> Decompose -> Target -> Implement -> Verify
```

После acceptance устанавливается `project.baseline: accepted`. Вся дальнейшая работа, включая новый service, входит как Change и использует те же primitives.

## Generic completion criteria

- Каждый claim имеет одну owning capability и полную traceability.
- Каждый ready slice имеет explicit typed Delta.
- Specification changes приняты до Decompose.
- Blocking Decisions terminal, normative consequences зеркалированы.
- Каждый production change имеет expected Red и Green evidence.
- Regression run покрывает declared unchanged behavior.
- Ни один affected Delta layer не потерян, ни один undeclared layer не изменён.
- Completed Change history архивируется целиком и исключается из default context.
