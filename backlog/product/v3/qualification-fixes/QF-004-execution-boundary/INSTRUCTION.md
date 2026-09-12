# QF-004 — реальная граница исполнения Worker

- **Приоритет:** P0
- **Зависимости:** QF-003 (inventory-diff и журнал уже в коде)
- **Commit:** `qualify: isolate worker command execution`
- **Исходный дефект:** [qualification-fix-plan.md, QF-004](../../qualification-fix-plan.md)
- **Код на момент написания:** commit `bb02820` + QF-001…QF-003

Исполнитель: читай [README.md](../README.md) до начала работы.

## 1. Дефект

`parse_shell_argv` в `scripts/qualify.py` разрешает по имени head-команды и
подкоманды, но не управляет опциями. Подтверждённые обходы:

1. `git diff --output=leak.txt` — «read-only» git пишет файл в произвольное
   место (glob `--output*` не экранирован).
2. `pytest` / `python -m pytest` исполняет Worker-authored Python (conftest,
   тесты) с доступом к host filesystem: можно читать judge pack
   (`process/bench/cases/**` с oracle и hidden_suite) и любые host-файлы.
   Судья изолирован только соглашением «score on a clean product tree», а не
   системной границей (`assert_sandbox_clean` в `src/deltafuse/bench/score.py`
   ловит только уже скопированный pack внутри sandbox).
3. Опции pytest `-p <module>` / `--load`, `-c/--config`, `-o addopts=...`,
   response-файлы `@file` — загрузка/выполнение произвольного кода и
   конфигурации, обходящей опции командной строки.

Исполнение сейчас — `subprocess.run(argv, shell=False, cwd=self.root)` в
`SandboxIO.shell`: наследуется полное окружение judge-процесса, judge pack
физически доступен по пути, отдельного процесса/контейнера нет.

## 2. Нормативное поведение

### 2.1 Точная политика subcommand/options (allowlist, не denylist)

Каждая разрешённая head-команда получает профиль: разрешённые подкоманды,
разрешённые флаги (точное сравнение токенов), форма позиционных аргументов.
Всё, что не разрешено явно, — отказ:

- `deltafuse <sub>` — sub ∈ существующего `DELTAFUSE_SUBCOMMANDS`; флаги:
  только `--json`, `--gate <имя>` (для advance), `--human` (для next);
  позиционных нет.
- `pytest` — флаги из фикс. множества: `-q`, `-x`, `-v`, `-s`, `-rA`,
  `--tb=line`, `--tb=short`, `--tb=no`; позиционные — только test-id /
  относительные пути без traversal (`tests/...`, `file.py::test`).
  Запрещены: любой токен, начинающийся с `-`, кроме перечисленных; `@`-файлы;
  `-p*`, `-c*`, `--config*`, `-o`, `--override-ini*`, `--rootdir`,
  `--pyargs`, `--import-mode*`, `-k`/`-m` разрешить (безопасны), `--co`
  разрешить.
- `python` — только пара `python -m pytest` + правила pytest выше; никакие
  другие флаги/скрипты.
- `git` — подкоманды `status|diff|log|show`, **опции запрещены полностью**
  (любой токен с ведущим `-` → отказ). Это закрывает `--output`,
  `--ext-diff`, `-O`, `--textconv` и т.п. Форматы вида `git diff HEAD`
  (позиционный rev) разрешить только как точный токен `HEAD`.

Дополнительно на уровне всех токенов (расширение текущего парсера):
запрещены `@`-префикс (response files), `=`-опции вне разрешённых флагов
(кроме `--gate`), UNC-пути (`\\server\share`), сетевые диски, повторяющиеся
`--` (разделитель конца опций).

### 2.2 Минимальное окружение и изоляция процесса

Qualification Worker исполняется в **staging root** (temp-каталог вне
репозитория framework), который готовит judge-сторона один раз на кампанию:

```
<staging>/
  venv/            # чистый venv: wheel deltafuse (pip wheel из чистого дерева)
                   # + pytest; НЕТ других пакетов
  work/<run_id>/   # копия sandbox (git-репозиторий из QF-003)
```

- Все команды Worker (deltafuse/pytest/python/git) выполняются с
  `cwd=<staging>/work/<run_id>`, PATH = `staging/venv` (+ каталог git),
  interpreter = `staging/venv` python (см. QF-005).
- **Judge pack в staging отсутствует физически**: `process/bench/cases/**`
  не копируется; переменные окружения с путями репозитория не передаются.
- По завершении run judge переносит `work/<run_id>` обратно в
  `bench/runs/.../sandbox` и скорит на judge-стороне (там pack есть).
- Точка подмены из QF-003: `SandboxIO` получает injectable корень исполнения
  и исполнитель команд — теперь это staging.

### 2.3 Сверка фактического diff после каждой команды

QF-003 inventory-diff вокруг каждой shell-команды теперь работает в staging;
изменения за пределами `work/<run_id>` (внутри staging) — нарушение
`staging_escape` (T7). Файл, созданный где-либо в staging вне work-каталога,
детектируется walker'ом judge-стороны после каждой команды (staging мал).

### 2.4 Threat model (обязательный документ)

Создать `backlog/product/v3/qualification-threat-model.md`:

- активы: judge pack (oracle/hidden_suite), host filesystem, thresholds,
  результаты кампании;
- границы и гарантии по уровням: (L1) политика argv + чистый venv + отсутствие
  pack в staging + минимальное окружение — гарантируется тестами на Windows
  и POSIX; (L2) OS-уровень (контейнер/VM, read-only host) — описан как
  опция, не требуется по умолчанию, с явной записью, что без L2
  Worker-authored Python в принципе может обращаться к host FS, и почему
  это приемлемо для qualification (pack отсутствует физически; критерии
  DF3-009 требуют отсутствия pack, а не полной OS-изоляции);
- платформенные гарантии Windows/POSIX раздельно (junction/symlink, PATH,
  env).

Ссылку на документ поместить в docstring `scripts/qualify.py`.

## 3. План работ

### Шаг 1 — Red-тесты (`tests/unit/test_qualify.py`, при необходимости новый
`tests/integration/test_qualify_boundary.py`)

Adversarial matrix (все обязаны падать до реализации):

- `test_git_output_option_rejected` — `git diff --output=leak.txt` и
  `git diff --output leak.txt` → ERROR; файл не создан.
- `test_git_any_option_rejected` — `git log --oneline`, `git status --porcelain`
  → ERROR (политика: опций нет вообще).
- `test_pytest_plugin_and_config_options_rejected` — `pytest -p evilmod`,
  `pytest -c cfg.ini`, `pytest -o addopts=-p:evil`, `pytest --rootdir ..`,
  `pytest @args.txt` → ERROR.
- `test_pytest_allowed_subset_still_runs` — `pytest -q`, `pytest --tb=line
  tests/smoke.py` (фикстура) → исполняется (exit=… не ERROR).
- `test_deltafuse_flag_policy` — `deltafuse next --json` OK;
  `deltafuse advance --gate implement` OK; `deltafuse next --evil` ERROR;
  `deltafuse next -- --json` ERROR.
- `test_response_file_and_dashdash_rejected` — `@file`, `--`, `--`
  комбинированные.
- `test_unc_and_network_paths_rejected` — `\\server\share\x`, `//server/x`,
  `Z:/x` → ERROR.
- `test_symlink_and_junction_escape_rejected` — создать symlink/junction
  внутри sandbox на внешний каталог (Windows: junction через существующий
  инструмент; POSIX: symlink) → `write_file` через него отклонён
  (resolve-guard), чтение через него — отклонено аналогично.
- `test_worker_python_cannot_read_judge_pack` — integration: в staging
  (фикстура staging root без pack) разрешённый `python -m pytest` исполняет
  тест, читающий путь judge pack (`process/bench/cases` оригинала) →
  тест-код получает «файл не найден»/отказ, маркер pack'а недоступен.
  Тест запускает реальный staging-механизм из 2.2.
- `test_staging_walk_detects_escape_file` — команда создаёт файл в
  `<staging>/leak.txt` (имитация) → walker после команды репортит
  `staging_escape`.

### Шаг 2 — Реализация

1. `parse_shell_argv`: переработать в политику профилей (2.1); функция
   возвращает `(argv | None, reason)` — причина отказа пишется в журнал
   события (QF-006 использует для классификации).
2. `StagingRoot` (новый модуль `scripts/qualify_staging.py` или секция в
   qualify.py): prepare (venv + wheel + pytest, без pack), per-run
   `work/<run_id>`, walker, teardown. Wheel: build один раз на кампанию
   (`pip wheel --no-deps`); сборка требует чистого bundle
   (`sync_assets --check` уже вызывается wheel-тестом; повторить здесь).
3. `SandboxIO.shell`: исполнение в staging (cwd=work, минимальный env —
   детали окружения доделает QF-005, здесь базовая гигиена: PATH=venv+git,
   без PYTHON*).
4. `run_case`: инициализация staging-work из sandbox, обратный перенос
   после run; scoring на judge-стороне как сейчас.
5. Walker после каждой команды (2.3); нарушения `staging_escape` → T7.
6. Threat model документ (2.4).

### Шаг 3 — Регрессия

- Полный suite; оба smoke. Внимание к существующим
  `test_adversarial_shell_commands_are_rejected` (расширить новыми
  командами матрицы — тест данных: список команд) и
  `test_allowed_shell_commands_still_run` (теперь должен исполняться в
  staging-фикстуре; `git status` в work-каталоге — git-репозиторий из
  QF-003 — ожидаемо exit=0).
- Время suite не должно вырасти катастрофически: staging-venv создаётся
  один раз на сессию тестов (module-scoped fixture с кэшем в tmp
  session), wheel reuse.

## 4. Границы и запреты

- Не запрещать pytest целиком — Worker обязан гонять свои тесты (это
  Red/Green evidence). Граница = staging + отсутствие pack + опции.
- Не выносить изоляцию в контейнер/VM как обязательную (документируется
  как L2-опция).
- Не менять CLI продукта и Core; всё в scripts/qualify* и тестах.

## 5. Acceptance

- [ ] Ни одна разрешённая команда не может писать вне sandbox/staging-work
      (матрица: output/config/plugin/import options, response files,
      symlink/junction, traversal, absolute/UNC — все RED→GREEN).
- [ ] Разрешённый тест-код не читает judge pack: pack физически отсутствует
      в staging (integration-тест зелёный).
- [ ] После каждой команды фактический diff сверяется; escape за work
      детектируется.
- [ ] Threat model с platform guarantees написан и привязан к runner.
- [ ] Полный suite + оба smoke зелёные на Windows; POSIX-ветки (symlink,
      env) покрыты тестами, исполняемыми через `sys.platform`-гейты с
      явным skip-обоснованием, если Windows-машина не позволяет.

## 6. Evidence для RESULT.md

1. Red-вывод матрицы (поимённо).
2. Green-вывод suite + smoke.
3. Листинг staging root кампании одного синтетического run (дерево без pack).
4. `git rev-parse HEAD` до/после.

## 7. Commit

Один commit: `qualify: isolate worker command execution`.
Состав: `scripts/qualify.py` (+ возможный `scripts/qualify_staging.py`),
`tests/unit/test_qualify.py` (+ возможный `tests/integration/test_qualify_boundary.py`),
`backlog/product/v3/qualification-threat-model.md`, `RESULT.md`.
