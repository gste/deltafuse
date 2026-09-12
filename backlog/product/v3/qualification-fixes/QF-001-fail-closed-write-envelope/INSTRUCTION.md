# QF-001 — fail-closed write envelope

- **Приоритет:** P0
- **Зависимости:** нет (первый пакет)
- **Commit:** `qualify: fail closed on missing write envelope`
- **Исходный дефект:** [qualification-fix-plan.md, QF-001](../../qualification-fix-plan.md)
- **Код на момент написания:** commit `bb02820`

Исполнитель: читай [README.md](../README.md) этой папки до начала работы —
там общие правила (Red→Green→регрессия, evidence, запреты).

## 1. Дефект

`SandboxIO.write_file` в `scripts/qualify.py` разрешает любую product-запись,
когда список envelope-глобов пуст:

```python
# scripts/qualify.py:292 (SandboxIO.write_file)
if self.write_globs and not is_exempt_path(rel_posix) and not path_in_envelope(rel_posix, self.write_globs):
    self.envelope_violations += 1
    return f"ERROR: {rel_posix} is outside the current envelope.write"
```

Пустой `write_globs` возникает в двух принципиально разных ситуациях:

1. **Core успешно ответил, и envelope.write действительно пуст** — Worker'у
   сейчас ничего писать нельзя.
2. **Core недоступен / вернул мусор** — `_core_envelope` глотает любое
   исключение и возвращает `[]`:

```python
# scripts/qualify.py:368-385 (_core_envelope)
try:
    with contextlib.redirect_stdout(buf):
        cli_main(["next", str(sandbox), "--json"])
    data = json.loads(buf.getvalue() or "{}")
except Exception:
    return []          # ОШИБКА Core неотличима от «пустого envelope»
```

В обоих случаях условие `if self.write_globs and ...` ложно, и запись в
`src/evil.py` проходит. Ошибка Core **расширяет** права Worker'а вместо того,
чтобы блокировать stage. Это подтверждено прямым probe в независимой проверке
№3 (см. `backlog/product/v3/release-report.md`, раздел 3).

Дополнительно: существующий тест кодирует дефект как норму —
`tests/unit/test_qualify.py::test_envelope_gated_write_rejected` (строки,
начинающиеся с `io2 = qualify.SandboxIO(tmp_path)`):

```python
# пустой envelope ... всё равно разрешает product-запись — это и есть дефект
io2 = qualify.SandboxIO(tmp_path)
assert "OK" in io2.write_file("docs/spec/x.md", "# x")
```

## 2. Нормативное поведение

1. `SandboxIO` различает три состояния write envelope:
   - `EnvelopeState(status="ok", globs=[...])` — Core ответил валидным JSON;
   - `EnvelopeState(status="ok", globs=[])` — Core ответил, писать нечего;
   - `EnvelopeState(status="error", detail=...)` — Core не ответил / non-zero
     exit / невалидный JSON / таймаут.
2. **Любое** из состояний `ok-empty`/`error` запрещает product-записи.
   Разрешены только: exempt-пути (`is_exempt_path`) и явно перечисленные
   внутренние файлы qualification (см. п. 4 ниже — на момент QF-001 такого
   списка нет, он пуст; QF-003 при необходимости расширит).
3. Состояние `error` дополнительно **блокирует stage**: попытка записи при
   `error` фиксируется как нарушение И как событие, из-за которого run
   помечается failed (см. п. 5 — как именно сигнализировать наверх).
4. `_core_envelope` больше никогда не возвращает «пустой список» как ответ на
   ошибку. Ошибка — это ошибка: она классифицируется и передаётся наверх.
5. Поведение `drive_worker`: ошибка получения envelope в начале вызова
   (строка `io.write_globs = _core_envelope(sandbox)`) не должна молча
   давать Worker'у полный доступ: при `status="error"` run завершается
   fail с явной причиной в `threshold_failures` (например,
   `T7 envelope_unavailable=<detail>`), а не продолжает цикл с полными правами.

## 3. План работ

### Шаг 1 — Red-тесты (в `tests/unit/test_qualify.py`)

Новые тесты (имена обязательны, сценарии ниже):

- `test_write_envelope_ok_empty_denies_product_writes` —
  `EnvelopeState(status="ok", globs=[])`: `write_file("docs/spec/x.md", ...)`
  и `write_file("src/evil.py", ...)` возвращают `ERROR`, счётчик
  `envelope_violations` растёт; exempt-путь (например `README.md`) пишется.
- `test_write_envelope_error_denies_and_flags` —
  `EnvelopeState(status="error", ...)`: любая product-запись отклонена,
  фиксируется отдельный признак `envelope_errors` (или эквивалент), который
  отличается от обычного `envelope_violations`.
- `test_core_envelope_malformed_json_is_error` — monkeypatch CLI
  `deltafuse next` на вывод мусора → `_core_envelope` возвращает/бросает
  состояние error, не `[]`.
- `test_core_envelope_nonzero_exit_is_error` — monkeypatch CLI exit code ≠ 0
  (например, sandbox без `.deltafuse/`) → состояние error.
- `test_drive_worker_fails_closed_when_envelope_unavailable` — небольшой
  стаб `worker_turn` (один вызов, action `write_file`) + monkeypatch
  `_core_envelope` → error: run-метрики содержат нарушение
  `envelope_unavailable`, verdict по T7 = fail.

Обновить существующий `test_envelope_gated_write_rejected`: блок с `io2`
меняется на ожидание отказа (`assert "ERROR" in io2.write_file(...)`); пустой
envelope без ошибки Core моделируется через явный `EnvelopeState("ok", [])`.

**Перед реализацией прогнать новые тесты и сохранить вывод (Red-фаза) в
RESULT.md — все обязаны падать.**

### Шаг 2 — Реализация (`scripts/qualify.py`)

1. Ввести `EnvelopeState` (dataclass или небольшой класс; типизация обязательна):
   ```python
   @dataclass
   class EnvelopeState:
       status: str                 # "ok" | "error"
       globs: list[str]
       detail: str | None = None
   ```
2. `_core_envelope(sandbox) -> EnvelopeState`:
   - успех и валидный JSON → `status="ok", globs=[...]`;
   - исключение, non-zero exit, пустой/невалидный stdout →
     `status="error", detail=<классифицированная причина>` (timeout / non-zero
     exit N / invalid JSON / no envelope key — при отсутствии ключа `envelope`
     в валидном ответе это `ok` с пустыми globs, как сейчас, но только если
     сам JSON распарсен и exit=0).
3. `SandboxIO`:
   - поле `write_envelope: EnvelopeState | None` (заменяет `write_globs`;
     `None` = envelope ещё не запрашивался — записи также запрещены,
     это тоже fail-closed);
   - `write_file`: отказ при `write_envelope is None or status != "ok"` или
     при `globs=[]` и непокрытом пути; отдельный счётчик/список
     `envelope_errors` для состояния error (не смешивать с
     `envelope_violations` — их семантика разная: нарушение против недоступности
     измерения);
   - в успехе записывать в `write_file` факт авторизации (список globs) —
     он понадобится QF-003 (`envelope_globs` события; см. конвенцию ToolEvent
     в README — заготовить поле можно уже сейчас).
4. `drive_worker`:
   - при `status="error"` после `_core_envelope` — не продолжать цикл с полным
     доступом: зафиксировать нарушение `envelope_unavailable` и прервать run
     (метрика `envelope_violations += 1` допустима для T7, но причина должна
     попадать в `threshold_failures`; простейший вариант — вернуть
     метрику `envelope_error: "<detail>"`, а `apply_thresholds` трактовает
     её как T7-fail);
   - обновить строку `io.write_globs = _core_envelope(sandbox)` на новое API.
5. `apply_thresholds`: если метрики содержат `envelope_error`, добавлять
   failure `T7 envelope_unavailable=<detail>` (независимо от значения
   `envelope_violations`).

### Шаг 3 — Регрессия

- Полный suite: `.venv/Scripts/python.exe -m pytest tests -q` — ожидается
  0 failed (включая обновлённый `test_envelope_gated_write_rejected`).
- Оба smoke: `pwsh -File tests/smoke-test.ps1` и `bash tests/smoke-test.sh`.
- `git status --porcelain` — только ожидаемые изменения.

## 4. Границы и запреты

- Не трогать `deltafuse.core.leash` (это ядро продукта, не qualify-раннер);
  раннер только потребляет `is_exempt_path` / `path_in_envelope`.
- Не ослаблять `ABSOLUTE` и `parse_shell_argv` (последний — территория QF-004).
- Не вводить «разрешённые внутренние файлы qualification» сверх exempt-путей
  Core: на этом этапе список пуст; если он понадобится, его введёт QF-003
  с явным перечислением.

## 5. Acceptance

- [ ] Разрешены записи только в пути, покрытые текущим Core envelope
      (`status="ok"`, непустые globs) или exempt-путями Core.
- [ ] `ok-empty` envelope отклоняет product-записи (тест есть).
- [ ] Любая ошибка Core (malformed JSON / non-zero exit / таймаут /
      исключение) даёт отказ записи, classified detail и fail по T7
      (тест на каждую ситуацию есть).
- [ ] Run с недоступным envelope завершается ненулевым exit code кампании
      (сквозной тест `drive_worker`/метрик).
- [ ] Все Red-тесты стали зелёными; полный suite зелёный; smoke зелёные.
- [ ] `RESULT.md` заполнен: команды, выводы Red/Green, итоговые counts.

## 6. Evidence для RESULT.md

1. Вывод `pytest tests/unit/test_qualify.py -q` в Red-фазе (до реализации).
2. Вывод полного suite + оба smoke в Green-фазе.
3. `git rev-parse HEAD` до и после; diff-статистика commit.

## 7. Commit

Один commit: `qualify: fail closed on missing write envelope`.
Состав: `scripts/qualify.py`, `tests/unit/test_qualify.py`,
`backlog/product/v3/qualification-fixes/QF-001-fail-closed-write-envelope/RESULT.md`.
