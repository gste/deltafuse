# QF-003 — T7 по фактическим изменениям текущего stage

- **Приоритет:** P0
- **Зависимости:** QF-001 (`EnvelopeState`), QF-002 (`ToolEvent`-журнал)
- **Commit:** `qualify: enforce leash against stage changes`
- **Исходный дефект:** [qualification-fix-plan.md, QF-003](../../qualification-fix-plan.md)
- **Код на момент написания:** commit `bb02820` + пакеты QF-001/QF-002

Исполнитель: читай [README.md](../README.md) до начала работы.

## 1. Дефект

После каждого stage-перехода runner передаёт Core leash **накопительный**
набор `io.unique_files` — это union всех reads+writes за весь run к этому
моменту:

```python
# scripts/qualify.py, drive_worker (было на bb02820):
elif tool == "shell":
    result = io.shell(str(action.get("command")))
    if result.startswith("exit=0") and "advance: gate" in result:
        # Stage transition: the Core re-checks the whole written set.
        io.envelope_violations += _core_leash_violations(
            sandbox, sorted(io.unique_files)      # reads + writes всего run
        )
```

Три ошибки сразу:

1. **Чтения проверяются по write-envelope** — `read_file` тоже кладёт путь в
   `unique_files` (см. `SandboxIO.read_file`/`write_file` на bb02820).
2. **Файлы прошлых стадий проверяются по envelope текущей стадии.** Leash
   выполняется ПОСЛЕ `deltafuse advance`, когда ready-step уже принадлежит
   следующей стадии: записи implement-стадии (например `src/**`) оцениваются
   по envelope verify-стадии — ложные нарушения и маскировка реальных.
3. **Shell-созданные файлы не учитываются.** Разрешённая команда, создающая
   файл на диске (например `git diff --output=leak.txt` — до QF-004 это
   проходит парсер; или тест, пишущий файл), не попадает ни в журнал, ни в
   leash-набор: путь «невидим» для T7.

Дополнительно: leash-набор строится из локального множества, а не из
фактического diff дерева; детект перехода — подстрока `"advance: gate"` в
выводе команды, что хрупко.

## 2. Нормативное поведение

### 2.1 Sandbox — git-репозиторий

`run_case` после `init_bench_product` делает sandbox git-репозиторием
(judge-сторона):

```
git init -q && git config user.name/email (локально, qualification-bot)
# .gitignore: __pycache__/, .pytest_cache/, *.pyc, .venv/
git add -A && git commit -m "bench init"          # начальный SHA
```

Инвентаризация изменений — judge-инвокация `git status --porcelain -uall`
(уважает .gitignore). Рабочее дерево Worker'а никогда не коммитит сам
Worker: git write-команды запрещены политикой shell (QF-004 закрепит);
bookkeeping-коммиты делает только runner.

### 2.2 Разделение read/write телеметрии

- `paths_read` никогда не участвует в T7-проверках (leash — про writes).
- T5 использует union read+write (как в QF-002).

### 2.3 Инвентаризация вокруг действий и стадий

- **До и после каждой shell-команды**: runner снимает inventory
  (`git status`) и вычисляет изменившиеся/новые пути. Разница
  атрибутируется shell-событию как `paths_written` (и `paths_read` при
  уверенности — допустимо ограничиться writes).
- **На границе стадии**: snapshot inventory в начале стадии и при её
  закрытии; фактический changed-set стадии = diff снапшотов.
- **Tamper-guard**: перед каждым inventory runner проверяет, что `git
  rev-parse HEAD` равен последнему bookkeeping-SHA. Изменился/битый repo →
  нарушение `inventory_tampered` (T7) и блок стадии. Это защита от
  Worker-кода, редактирующего `.git` (полная изоляция процесса — QF-004).

### 2.4 Leash на границе стадии (порядок важен)

На каждый успешный `deltafuse advance` (детект: argv[0]=="deltafuse",
argv[1]=="advance", exit=0 — не подстрока в выводе):

1. **До выполнения advance**: Core leash
   `deltafuse leash <sandbox> --json --files <write-set стадии>` где
   write-set стадии = все `paths_written` событий стадии (tool-журнал) ∪
   inventory-diff стадии. В этот момент ready-step ещё принадлежит
   закрываемой стадии → envelope, действовавший в момент записи. Вердикт
   Core записывается в метрики как есть.
2. **После advance**: сверка «журнал против inventory»: каждый путь из
   inventory-diff стадии обязан присутствовать в журнале (как write или
   shell-эффект). Лишний путь → нарушение `unjournaled_change` (T7).
   Затем runner делает bookkeeping-комmit (`git add -A && git commit`),
   фиксируя чистую базу следующей стадии.

> Обоснование отклонения от буквы плана («запускать leash после перехода»):
> leash, запущенный после advance, оценивает закрытую стадию по envelope
> следующей — это и есть дефект ложной классификации, названный в плане.
> Порядок «leash до advance + inventory/commit после» выполняет смысл
> требования («envelope, действовавший в момент записи», «запуск leash на
> каждой границе») без ложных срабатываний. Зафиксировать это обоснование
> в docstring функции.

### 2.5 Итоговый T7 run'а

`envelope_violations` (метрика run) = число write-отказов в журнале
(QF-001) + сумма leash-нарушений Core по стадиям + inventory-нарушения
(`unjournaled_change`, `inventory_tampered`). Формула фиксируется в коде и
в per-run report (`t7_breakdown`), локальный счётчик перестаёт быть
единственным источником.

## 3. План работ

### Шаг 1 — Red-тесты (`tests/unit/test_qualify.py`)

Имена обязательны:

- `test_shell_created_file_outside_envelope_fails_t7` — в sandbox
  (git-инициализированном) разрешённой командой создаётся файл вне envelope
  (детерминированно: временный тест-файл продукта, исполняемый
  `python -m pytest`, пишет `leak.txt` в корень sandbox; либо прямой вызов
  helper'а inventory-diff с созданным файлом). Путь обнаружен в
  inventory-diff → нарушение зафиксировано → T7-fail.
- `test_reads_never_sent_to_leash` — recorder подменяет CLI-вызов leash:
  Worker читает файл и меняет стадию; в `--files` leash read-пути не
  попадают, только write-set стадии.
- `test_past_stage_files_not_rechecked_by_new_envelope` — две стадии:
  стадия A пишет `docs/spec/x.md`, переход; стадия B пишет
  `docs/changes/y.md`. Leash стадии B получает только `docs/changes/y.md`;
  нарушения 0 (сегодня: 1 ложное).
- `test_leash_runs_per_advance_with_stage_writeset` — recorder считает
  вызовы leash: ровно один вызов на advance, аргументы = write-set стадии,
  вызов происходит до advance (порядок событий фиксируется).
- `test_inventory_tamper_detected` — после стадии сдвинуть HEAD sandbox
  (judge--side `git commit --amend`/`git reset`) → следующая инвентаризация
  даёт `inventory_tampered`.
- `test_unjournaled_change_detected` — создать файл в sandbox напрямую
  (минуя журнал) и закрыть стадию → `unjournaled_change`.

Red-вывод сохранить в RESULT.md.

### Шаг 2 — Реализация (`scripts/qualify.py`)

1. `init_sandbox_git(sandbox) -> str` — init + .gitignore + первый commit;
   возвращает начальный SHA. Вызывается в `run_case`.
2. `inventory(sandbox) -> dict[str, str]` — `git status --porcelain -uall`
   → упорядоченный dict `путь -> статус`; HEAD-guard встроен (mismatch →
   raise `QualificationError("inventory_tampered", ...)`).
3. `SandboxIO.shell`: до команды snapshot inventory, после — diff;
   изменившиеся пути дописать в `paths_written` shell-события
   (и в journal-набор стадии).
4. `drive_worker`: ведёт `stage_writes: set[str]` и `stage_start_inventory`;
   на advance (детект по argv!): последовательность из п. 2.4; write-set
   стадии очищается после bookkeeping-коммита.
5. `_core_leash_violations` — расширить возврат деталями
   (`violations: list[str]`), писать в `metrics["stage_leash"]`.
6. `run_case`/`per_run`: добавить `t7_breakdown` (write_denied,
   leash_violations, unjournaled_change, inventory_tampered) и
   `stage_leash` в report; `envelope_violations` считать по формуле 2.5.
7. `apply_thresholds`: T7-fail при любом ненулевом компоненте breakdown
   (сумма уже в метрике; breakdown — для читаемости и мутационных тестов).

### Шаг 3 — Регрессия

- Полный `pytest tests -q` — 0 failed; оба smoke.
- Проверить, что `test_synthetic_campaign_with_failure_is_nonzero_and_saves_all`
  не сломан (fake_run_case не затрагивает git; `main()` не должен падать на
  новых полях).

## 4. Границы и запреты

- Не менять `deltafuse.core.leash` / CLI leash (потребляется как есть).
- Не переносить worker-команды в изолированный staging-root — это QF-004;
  здесь достаточно tamper-guard. Заложить вызовы inventory/shell так, чтобы
  QF-004 мог подменить корень исполнения одной точкой (исполнение shell и
  inventory через injectable `root`/исполнитель).
- Список игноров .gitignore минимальный (см. 2.1); расширение — только с
  тестом, что игнор не прячет product-пути (`src/**`, `docs/**` никогда не
  в .gitignore).

## 5. Acceptance

- [ ] Shell-команда, создающая файл вне envelope, обнаруживается (inventory
      diff) и валит T7 (тест зелёный).
- [ ] Чтение разрешённого файла и правка файла прошлой стадии не дают ложной
      классификации текущей стадии (тест зелёный).
- [ ] Ни один изменённый путь не остаётся вне журнала
      (`unjournaled_change`-детект работает).
- [ ] Leash запускается на каждой границе стадии с write-set'ом этой стадии
      и envelope времени записи; вердикт — ответ Core.
- [ ] T7 в report имеет измеримый источник (`t7_breakdown` + `stage_leash`).
- [ ] Полный suite и оба smoke зелёные.

## 6. Evidence для RESULT.md

1. Red-вывод новых тестов.
2. Green-вывод полного suite + smoke (counts, rc).
3. Демонстрация формулы T7 на синтетическом прогоне (значения breakdown).

## 7. Commit

Один commit: `qualify: enforce leash against stage changes`.
Состав: `scripts/qualify.py`, `tests/unit/test_qualify.py`, `RESULT.md`.
