# q6: пути записи Change берутся из `workflow.code_roots`, а не только корневые `src/**` и `tests/**`

**Состояние: сделано 2026-10-08, ветка `fix/code-roots-write-paths`; ответы владельца: `allowed_read` — да, версия 3.3.8.** Было: постановка, к исполнению в отдельном чате DeltaFuse. Записано 2026-10-08 по сквозному Change
на выходе Fuse-Back (`fuseback/docs/planning/E2E-CHANGE-J03.md`). Решение владельца: делать.

Тип работы: изменение ядра DeltaFuse, отдельная ветка и PR (как [`dir/*`](CODE-ROOT-DIRECT-FILES.md)).
Сливает и ставит тег владелец; `git push` и слияние исполнитель не делает.

## Проблема

На маршруте `code` задача Change пишет только в корневые `src/**` и `tests/**`. В многомодульном
Maven/Gradle-проекте код и тесты лежат в `<module>/src/main/java` и `<module>/src/test/java`, в
Python-репозитории без src-layout — в `<package>/` (Python-Markdown: `markdown/`). Ни один Change в таком
репозитории не проходит `decomposed`.

Ключ для этого уже объявлен и не действует: `validate-config` принимает `workflow.code_roots`
(`core/config.py`:156–163, «list of glob paths like 'src/**'»), `leash.capability_roots()` (:440) его читает —
и ни одна проверка эту функцию не вызывает.

Ядро уже знает о такой раскладке: `ownership.change_code_paths` (:142) сознательно не использует
`CODE_WRITE_GLOBS` — «a service repository keeps code in `document-service/...` (bench case J03), outside
`src/**`».

### Наблюдение (DeltaFuse 3.3.7, J03 после Fuse-Back)

Change `CHG-001-trail-filter-null-kind` прошёл intake, analyze, specify и шлюз спецификации; задача
`allowed_paths: [audit-service/src/main/java/.../LegacyTrailFilter.java, audit-service/src/test/java/.../LegacyTrailFilterCharacterizationTest.java]`:

```
advance failed: gate 'decomposed' failed:
TASK-001.md: allowed_paths: 'audit-service/src/main/java/...' is outside the phase contract
Task TASK-001: allowed_paths 'audit-service/src/main/java/...' is outside what this Change may write; use paths under src/**, tests/**, docs/spec/**
Gate decomposed: Task TASK-001 promises requirement_delta 'modified' but may change no product file ...
```

С `workflow.code_roots: [audit-service/src/**, document-service/src/**, …]` в `config.yaml` — те же три
сообщения.

### Воспроизведение без Fuse-Back

Временный продукт: `deltafuse init`, git, модуль `svc/src/main/java/A.java`, `svc/src/test/java/ATest.java`,
каталог с `active` capability `code_roots: [svc/src/main/java/]`, `workflow.code_roots: [svc/src/**]`.
Change до `decomposed` с задачей `allowed_paths: [svc/src/main/java/A.java, svc/src/test/java/ATest.java]`,
`requirement_delta: modified` → `advance --gate decomposed` отказывает тремя сообщениями выше. Это и есть
красный тест интеграционного уровня (см. «Красные тесты»).

## Где зашито

| место | что | кто читает |
| --- | --- | --- |
| `core/context.py`:31 `PHASE_CONTRACTS` — `declare` (:81, :84), `implement` (:93–98), `verify` (:110) | `src/**`, `tests/**` в `allowed_read` / `allowed_write` | `phase_allowed_paths`, `phase_write_globs` (:466, :474), `task_write_globs` (:492), `validate_paths_against_globs` (:497, «outside the phase contract»); `queue.py`:1006 (`allowed_read`/`allowed_write` в `deltafuse next`); `leash.envelope_write_globs` (:184), `leash.py`:230 |
| `core/context.py`:124 `_PRODUCT_CODE_GLOBS`, `is_product_code_path` (:189) | `src/**`, `tests/**` | `fsm.py`:365, :1119 |
| `core/leash.py`:38 `CODE_WRITE_GLOBS`, `is_product_path` (:294) | `src/**`, `tests/**`, `deploy/**`, `docs/ops/**`, `ops/**` | git-хук leash (:966) |
| `core/leash.py`:437 `DEFAULT_CAPABILITY_ROOTS`, `task_envelope_errors` (:469, :503) | `src/**`, `tests/**`, `docs/spec/**` | «outside what this Change may write» |
| `core/leash.py`:529 `unreachable_green_errors` (:547) | `phase_write_globs("…", "code")` | «may change no product file» |
| `core/leash.py`:440 `capability_roots()` | читает `workflow.code_roots` | **никто** |

`steps.py`:34 сверяет `STEP_CONTRACTS` с `PHASE_CONTRACTS` — менять согласованно.

## Решение

1. **Одна функция корней кода маршрута `code`:** `code_write_globs(product_root) -> tuple[str, ...]` —
   `workflow.code_roots` из `.deltafuse/config.yaml`, если задан и не пуст; иначе `("src/**", "tests/**")`.
   `capability_roots()` либо становится ею, либо удаляется (сейчас мёртвая).
2. **Контракты фаз зависят от продукта.** Глобы `src/**`/`tests/**` в `PHASE_CONTRACTS` для `declare`,
   `implement`, `verify` подставляются из `code_write_globs(product_root)`: функции `phase_allowed_paths`,
   `phase_write_globs`, `task_write_globs` получают `product_root` (по умолчанию `None` → как сейчас).
   Вызовы — `queue.py`, `leash.py`, `fsm.py` — передают корень продукта, он у них есть.
3. **`is_product_code_path`, `is_product_path`, `task_envelope_errors`, `unreachable_green_errors`** берут
   глобы кода из той же функции. `deploy/**`, `docs/ops/**`, `ops/**` и маршруты `docs`/`ops` не меняются.
4. **Код и тесты модуля — под одним глобом** (`svc/src/**`): так их держат Maven и Gradle. Declare и
   Implement различаются задачами и `allowed_paths`, не глобами; разделять `main`/`test` ядру не нужно.
5. **Обратная совместимость:** без ключа поведение прежнее, все существующие тесты проходят без правок.
   Ключ, который сегодня молча игнорируется, начинает действовать — запись в CHANGELOG об этом прямо.

Не делать: выводить корни записи из каталога (`code_roots` + `test_roots` активных capability) — связывает
контракт фаз с каталогом и статусами, routing и так ограничивает Change своими capability; расширять
константы до `**/src/**` — пускает запись в любой вложенный `src` (vendored-код, примеры).

## Красные тесты (сначала, должны упасть по описанной причине)

В `tests/unit/test_leash.py` / `tests/unit/test_context.py` (или соседнем файле):

1. с `workflow.code_roots: [svc/src/**]` `task_envelope_errors` не возвращает ошибку для
   `svc/src/main/java/A.java`; для `other/B.java` возвращает ошибку с перечнем корней из конфига;
2. `phase_write_globs("implement", "code", product_root)` содержит `svc/src/**` и не содержит `src/**`;
   без ключа — как сейчас;
3. `unreachable_green_errors` видит `svc/src/main/java/A.java` как продуктовый файл;
4. `is_product_path("svc/src/main/java/A.java")` для продукта с ключом — `True` (хук leash);
5. `deltafuse next --json` на шаге implement отдаёт `allowed_read`/`allowed_write` с `svc/src/**`;
6. интеграционный: продукт из «Воспроизведения» проходит `advance --gate decomposed`.

## Критерий приёмки

- все шесть тестов зелёные; без ключа существующие тесты не менялись и проходят;
- полный набор DeltaFuse зелёный (судить по коду возврата);
- `docs/context-model.md` и `.ru`: абзац про `workflow.code_roots` — что он задаёт корни записи маршрута
  `code`, значение по умолчанию, пример многомодульного Maven;
- `docs/contracts/leash.md` и `.ru`: корни записи кода берутся из `workflow.code_roots` (git-хук и `deltafuse leash`);
- `CHANGELOG.md`: запись под следующей версией; версия — открытый вопрос 2.

## После принятия — в Fuse-Back (не часть этого PR)

- `runner` для многомодульного проекта пишет `workflow.code_roots` по найденным модулям;
- `handoff`, проверка `change-paths` (FR-HND-6): засчитывать `workflow.code_roots`, если установленный
  DeltaFuse его применяет — зондом, как для `dir/*`;
- повторить Change `CHG-001-trail-filter-null-kind` на J03 до `converged`.

## Открытые вопросы владельцу

1. `allowed_read` фаз тоже из `workflow.code_roots` — предложение «да», иначе Worker не видит код модуля.
2. Версия: 3.3.8 как исправление (ключ был объявлен и не работал) или минорная.

Источник: `fuseback/docs/planning/E2E-CHANGE-J03.md`, 2026-10-08.
