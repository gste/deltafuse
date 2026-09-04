# State Machine

State хранится в metadata каждого артефакта. Перемещение директорий не кодирует активное состояние, кроме архивирования завершённого Change.

## Project baseline

`.deltafuse/config.yaml` содержит:

```yaml
project:
  baseline: draft | accepted
```

- `draft`: Bootstrap может выделять capabilities и создавать initial specification pack; implementation заблокирован.
- `accepted`: разрешён обычный Change workflow.

Bootstrap и Change используют одни primitives. Создание нового сервиса в репозитории с принятой baseline является большим Change, а не повторным Bootstrap.

## Change states

```text
normalized
  -> analyzing
  -> blocked-on-decision
  -> analyzed
  -> specification-proposed
  -> specified
  -> decomposed
  -> targeting
  -> target-confirmed
  -> implementing
  -> implemented
  -> verifying
  -> converged
  -> archived
```

Альтернативные terminal states: `rejected`, `duplicate`, `not-reproduced`, `superseded`.

| From | To | Gate |
|---|---|---|
| none | `normalized` | Intake создал immutable claims и provenance |
| `normalized` | `analyzing` | Capability catalog существует либо создаётся Bootstrap profile |
| `analyzing` | `blocked-on-decision` | Хотя бы один blocking Decision имеет `status: proposed` |
| `blocked-on-decision` | `analyzing` | Relevant Decisions стали terminal или были уточнены |
| `analyzing` | `analyzed` | Claims маршрутизированы, typed deltas созданы, global reconciliation завершён |
| `analyzed` | `specification-proposed` | Normative specification delta требует приёмки |
| `analyzed` | `specified` | `requirement_delta: none` доказан exact accepted spec refs |
| `specification-proposed` | `specified` | Spec edits приняты и проверены |
| `specified` | `decomposed` | Каждый slice покрыт executable tasks |
| `decomposed` | `targeting` | Выбрана ready task |
| `targeting` | `target-confirmed` | Frozen target падает по ожидаемой причине |
| `target-confirmed` | `implementing` | Production-code scope разрешён task contract |
| `implementing` | `implemented` | Target стал Green, scoped regressions прошли |
| `implemented` | `verifying` | Все tasks находятся в terminal state |
| `verifying` | `converged` | Все объявленные delta projections fused и подтверждены evidence |
| `converged` | `archived` | Change удалён из active index и архивирован целиком |

Если downstream-шаг обнаружил отсутствующее нормативное поведение или новый существенный выбор, Change возвращается в `analyzing`. Downstream-agent не исправляет upstream-артефакт молча.

## Slice states

```text
draft -> analyzing -> blocked -> analyzed -> specified -> decomposed -> verified
```

Каждый slice имеет одну primary capability, один independently verifiable outcome, exact refs, dependencies и собственный context budget.

## Task states

```text
pending -> targeting -> target-confirmed -> implementing -> implemented -> verified
```

Альтернативы: `blocked`, `cancelled`, `superseded`.

Tasks остаются внутри Change после выполнения и архивируются вместе с ним. Завершённая task history не удаляется.

## Decision states

```text
proposed -> accepted | rejected | superseded
```

Proposed Decision может представлять ещё не решённый продуктовый или технический вопрос. Только terminal Decisions разблокируют анализ. Accepted Decision, меняющий observable behavior, contract, policy или обязательный invariant, зеркалируется в `docs/spec/**` до implementation.

## Framework version

`change.yaml` фиксирует framework и schema versions, использованные при Intake. Активный Change завершается на этой версии или явно мигрируется целиком; installer update не меняет его semantics молча.
