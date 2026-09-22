# Контракт Artifact Writer v1

**Версия контракта:** 1  
**Целевая схема хранения:** v3  
**Версия фреймворка:** 3.2.0  
**Schema URI:** `https://deltafuse.dev/contracts/artifact-writer/v1`  
**Receipt Schema URI:** `https://deltafuse.dev/contracts/artifact-writer/receipt/v1`  

## 1. Обзор

Контракт Artifact Writer определяет транспортный конверт типизированных операций, дескрипторы операций, структуру квитанций, протокол патчей и диагностику ошибок для службы сериализации DeltaFuse Core.

Он служит протоколом сериализации и сохранения между клиентами (Worker, хост-обёртками, CLI) и хранилищем DeltaFuse Core. Он **не** даёт полномочий изменять поля, принадлежащие Core, или выполнять переходы жизненного цикла.

---

## 2. Конверт операций

Все запросы операций передаются в закрытом JSON/YAML конверте, прошедшем валидацию по `docs/contracts/artifact-writer.schema.yaml`:

```yaml
request_id: "req-001"
operation: "create" # create | update | validate | describe
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
- `operation`: Обязательный enum (`create`, `update`, `validate`, `describe`, `update-index`).
- `kind`: Обязательный enum, соответствующий одной из 10 схем хранения.
- `change`: Идентификатор владения Change или относительный путь к директории.
- `identity`: Идентификатор конкретного артефакта (например, `TASK-001`) для `create` / `describe`.
- `target`: Относительный путь к файлу (например, `tasks/TASK-001.md`) для `update` / `validate`.
- `expected_sha256`: Опциональный хэш SHA256 целевого файла до обновления (контроль параллелизма).
- `semantic_payload`: Объект с начальными семантическими полями при `create`.
- `patch`: Объект с правками JSON Pointer при `update`.
- `body`: Опциональное непрозрачное тело документа Markdown.
- `update-index`: Атомарная операция синхронизации списков дочерних элементов в `change.yaml` с диска.

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
| `task` | `create`, `update`, `validate`, `describe` | `title`, `kind`, `depends_on`, `requirement_delta`, `spec_refs`, `design_ref`, `allowed_paths`, `forbidden_paths`, `context_budget` | `id`, `change`, `slice`, `status` |
| `slice` | `create`, `update`, `validate`, `describe` | `title`, `primary_capability`, `related_capabilities`, `policies`, `spec_refs`, `claims`, `depends_on`, `context_budget` | `id`, `change`, `status` |
| `spec-delta` | `create`, `update`, `validate`, `describe` | `slices`, `added`, `modified`, `removed` | `change`, `status` |
| `routing` | `create`, `update`, `validate`, `describe` | `claims` | `change` |
| `change` | `update`, `validate`, `describe` | `title`, `intent`, `risk`, `source/request`, `source/intake_refs`, `analysis/summary` | `schema_version`, `id`, `status`, `framework`, `analysis/routing`, `deltas`, `slices`, `decisions`, `tasks`, `verification` |
| `decision` | `validate`, `describe` | `title`, `kind`, `owner`, `date`, `affects`, `supersedes`, `superseded_by` | `id`, `change`, `status` |
| `evidence` | `validate`, `describe` | Нет | Все поля (штампуются ядром) |
| `coverage` | `validate`, `describe` | Нет | `change`, `claims` |
| `capability` | `validate`, `describe` | Нет | `schema_version`, `domains`, `policies` |
| `lock` | `validate`, `describe` | Нет | `schema_version`, `framework` |

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
- `0`: Успех / успешная read-only валидация.
- `2`: Ошибка ввода, конверта или валидации схемы.
- `3`: Отказ в авторизации или попытка записи полей Core.
- `4`: Несовпадение целевого SHA256 или ошибка блокировки параллелизма.
- `5`: Ошибка сохранения или неопределённое состояние транзакции.

Отсутствующий или повреждённый установленный контракт Writer возвращает код `5`
и `asset_resolution_failed` (этап `schema`, путь `/`, сообщение не длиннее 512
символов). Изменения не выполняются; контракт из текущего каталога вызывающей
стороны не используется. Переустановите проверенный bundle или пересоздайте его
командой `scripts/sync_assets.py` при разработке из исходников.
