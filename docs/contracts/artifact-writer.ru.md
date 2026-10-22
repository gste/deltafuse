# Контракт Artifact Writer v1

**Версия контракта:** 1  
**Целевая схема хранения:** v3  
**Версия фреймворка:** 3.3.9 (документ описывает её)  
**Schema URI:** `https://deltafuse.dev/contracts/artifact-writer/v1`  
**Receipt Schema URI:** `https://deltafuse.dev/contracts/artifact-writer/receipt/v1`  

## 1. Обзор

Контракт Artifact Writer определяет транспортный конверт типизированных операций, дескрипторы операций, структуру квитанций, протокол патчей и диагностику ошибок для службы сериализации DeltaFuse Core.

Он служит протоколом сериализации и сохранения между клиентами (Worker, хост-обёртками, CLI) и хранилищем DeltaFuse Core. Он **не** даёт полномочий изменять поля, принадлежащие Core, или выполнять переходы жизненного цикла.

Команда воркера — `deltafuse artifact write --kind <kind> --change <change-dir> --input <json|->`: воркер называет артефакт (`identity` или `target`), а ядро решает, `create` это или `update`, и само ведёт индекс дочерних элементов в `change.yaml`. Операции `describe`, `validate` и `update-index` и подкоманды `artifact create|update|describe|validate|update-index` удалены в 3.3.9; служба сохраняет `create` и `update`.

---

## 2. Конверт операций

Все запросы операций передаются в закрытом JSON/YAML конверте, прошедшем валидацию по `docs/contracts/artifact-writer.schema.yaml`:

```yaml
request_id: "req-001"
operation: "create" # create | update
kind: "task"        # task | slice | spec-delta | routing | change | ...
change: "CHG-001"
identity: "TASK-001"
semantic_payload:
  title: "Add authentication handler"
  kind: "feature"
  allowed_paths: ["src/auth.py"]
```

### Поля:
- `request_id`: Обязательный строковый идентификатор для отслеживания транзакций и идемпотентности.
- `operation`: Обязательный enum (`create`, `update`). Его ставит `deltafuse artifact write`, а не воркер.
- `kind`: Обязательный enum, соответствующий одной из 10 схем хранения.
- `change`: Идентификатор владения Change или относительный путь к директории.
- `identity`: Идентификатор конкретного артефакта (например, `TASK-001`); обязателен для `create`.
- `target`: Относительный путь к файлу (например, `tasks/TASK-001.md`) для `update`.
- `expected_sha256`: Опциональный хэш SHA256 целевого файла до обновления (контроль параллелизма).
- `semantic_payload`: Объект с начальными семантическими полями при `create`.
- `patch`: Объект с правками JSON Pointer при `update`.
- `body`: Опциональное непрозрачное тело документа Markdown.

---

## 3. Семантика патчей

Обновления используют явный язык патчей JSON Pointer (свойство `patch`):

```yaml
patch:
  set:
    - path: "/title"
      value: "Updated Auth Title"
  remove:
    - "/design_ref"
  canonicalize_metadata: false
```

### Правила:
- `set`: Список объектов `{path, value}`. `path` ДОЛЖЕН быть валидным JSON Pointer, начинающимся с `/`.
- `remove`: Список строк JSON Pointer, начинающихся с `/`. Нельзя удалять обязательные по схеме поля.
- `canonicalize_metadata`: Булевский флаг авторизации переупорядочивания/переформатирования frontmatter, если исходный frontmatter отличается от канонического вывода кодека.
- Цели указателей ДОЛЖНЫ соответствовать изменяемым семантическим полям, определённым в дескрипторе типа. Поля Core (`/status`) отклоняются.

---

## 4. Дескрипторы операций по типам

Дескрипторы операций находятся в `process/artifact-operations/*.descriptor.yaml` и индексируются в `process/artifact-operations/manifest.json`.

| Тип | Допустимые операции | Допустимые семантические поля | Поля Core |
|---|---|---|---|
| `task` | `create`, `update` | `title`, `kind`, `depends_on`, `requirement_delta`, `spec_refs`, `design_ref`, `allowed_paths`, `forbidden_paths`, `context_budget` | `id`, `change`, `slice`, `status` |
| `slice` | `create`, `update` | `title`, `primary_capability`, `related_capabilities`, `policies`, `spec_refs`, `claims`, `depends_on`, `context_budget` | `id`, `change`, `status` |
| `spec-delta` | `create`, `update` | `slices`, `added`, `modified`, `removed` | `change`, `status` |
| `routing` | `create`, `update` | `claims` | `change` |
| `change` | `update` | `title`, `intent`, `risk`, `source/request`, `source/intake_refs`, `analysis/summary` | `schema_version`, `id`, `status`, `framework`, `analysis/routing`, `deltas`, `slices`, `decisions`, `tasks`, `verification` |
| `decision` | `create`, `update` (только пока `proposed`) | `title`, `kind`, `owner`, `date`, `affects`, `supersedes`, `superseded_by` | `id`, `change`, `status` |
| `evidence` | Нет (пишет `deltafuse evidence`) | Нет | Все поля (штампуются ядром) |
| `coverage` | Нет (пишет `deltafuse coverage`) | Нет | `change`, `claims` |
| `capability` | Нет | Нет | `schema_version`, `domains`, `policies` |
| `lock` | Нет | Нет | `schema_version`, `framework` |

---

## 5. Долговечные квитанции

Каждая мутирующая операция возвращает квитанцию по `process/artifact-operations/receipt.schema.yaml`:

- `request_id`, `transaction_id`, `timestamp`
- `operation`, `kind`, `target`
- `operation_schema` (версия и хэш)
- `storage_schema` (тип, версия=3, id, хэш)
- `serializer_revision` (целое число)
- `request_sha256`, `payload_sha256`, `previous_sha256`, `result_sha256`
- `changed` (булев флаг изменений)
- `outcome` (`prepared`, `published`, `committed`, `recovered`, `failed`)
- `authority` (`actor`, `work_item`, `product_root`)
- `validation_scopes` (статусы валидации схемы, политик и ссылок)
- `receipt_sha256` (хэш квитанции без себя)

---

## 6. Коды выхода и диагностика ошибок

Коды выхода CLI:
- `0`: Успех.
- `2`: Ошибка ввода, конверта или валидации схемы.
- `3`: Отказ в авторизации или попытка записи полей Core.
- `4`: Несовпадение целевого SHA256 или ошибка блокировки параллелизма.
- `5`: Ошибка сохранения или неопределённое состояние транзакции.

Отсутствующий или повреждённый установленный контракт Writer возвращает код `5`
и `asset_resolution_failed` (этап `schema`, путь `/`, сообщение не длиннее 512
символов). Изменения не выполняются; контракт из текущего каталога вызывающей
стороны не используется. Переустановите проверенный bundle или пересоздайте его
командой `scripts/sync_assets.py` при разработке из исходников.
