# QF-005 — контролируемый Python и environment

- **Приоритет:** P0
- **Зависимости:** QF-004 (staging root и базовая гигиена окружения уже есть)
- **Commit:** `qualify: pin interpreter and environment`
- **Исходный дефект:** [qualification-fix-plan.md, QF-005](../../qualification-fix-plan.md)
- **Код на момент написания:** commit `bb02820` + QF-001…QF-004

Исполнитель: читай [README.md](../README.md) до начала работы.

## 1. Дефект

Разрешённая команда `python -m pytest` исполняется как есть:

```python
# scripts/qualify.py, SandboxIO.shell (bb02820):
proc = subprocess.run(
    argv,
    shell=False,
    cwd=str(self.root),
    ...
)
```

`subprocess.run` без `env=` наследует окружение judge-процесса, а `python`
разрешается через `PATH`. Независимый suite упал на
`tests/unit/test_qualify.py::test_allowed_shell_commands_still_run`:
выбранный из PATH интерпретатор не содержал pytest. Значит:

- результат зависит от случайного Python в PATH машины (Windows: Store-
  shim, другая версия; POSIX: системный python без pytest);
- Worker-команды видят `PYTEST_ADDOPTS`, `PYTEST_PLUGINS`, `PYTHONPATH`,
  `PYTHONHOME`, прокси и любые переменные judge-окружения — это
  Worker-controlled injection через env, которого Core не авторизовал.

После QF-004 команды уже исполняются в staging; этот пакет доводит
интерпретатор и окружение до контролируемого состояния и чинит падающий
тест.

## 2. Нормативное поведение

1. **Interpreter pin.** На исполнении argv канонизируется:
   - `python …` → `<staging>/venv/Scripts/python.exe` (Windows) /
     `<staging>/venv/bin/python` (POSIX) — интерпретатор staging-venv,
     выбранный runner'ом, не PATH;
   - `pytest …` → `<venv-python> -m pytest …`.
   Парсер по-прежнему принимает буквальные `python -m pytest` / `pytest`
   (argv-контракт Worker не меняется); подмена происходит на границе
   исполнения.
2. **Минимальное окружение.** `env` конструируется с нуля (allowlist):
   - Windows: `PATH=<venv Scripts>;<git dir>`, `SYSTEMROOT`, `SYSTEMDRIVE`,
     `COMSPEC`, `PATHEXT`, `TEMP`/`TMP` (перенаправлены в staging);
   - POSIX: `PATH=<venv bin>:/usr/bin:/bin`, `HOME=<staging>/home`,
     `TMPDIR=<staging>/tmp`.
   Всё остальное (включая `PYTHON*`, `PYTEST_*`, `DELTAFUSE_*`, прокси,
   переменные с путями репозитория) не передаётся. `cwd` = work-каталог
   staging (QF-004).
3. **Отказ при неизвестных переменных.** Команда с токеном вида
   `KEY=VALUE` (попытка env-override через argv) отклоняется парсером
   (`=` уже ограничен QF-004; закрепить тестом отдельный кейс
   `PYTEST_ADDOPTS=-x` как argv-токен).
4. Один и тот же argv-контракт проходит на Windows и POSIX и не зависит от
   случайного Python в PATH.

## 3. План работ

### Шаг 1 — Red-тесты (`tests/unit/test_qualify.py`)

- `test_python_resolved_to_pinned_interpreter` — подготовить каталог с
  фальшивым `python` (скрипт, пишущий маркер и возвращающий код 1), поставить
  его ПЕРВЫМ в `os.environ["PATH"]` теста; `io.shell("python -m pytest
  --version")` обязан вернуть exit=0 (или хотя бы не задеть фальшивый
  интерпретатор: маркер не создан) — сегодня упадёт, потому что возьмётся
  фальшивый python. Идёмпотентно на обеих платформах (фальшивка — `.bat`
  на Windows, скрипт с shebang на POSIX).
- `test_pytest_head_resolved_to_module` — `io.shell("pytest --version")`
  исполняется pinned-интерпретатором (`sys.executable -m pytest`), exit=0.
- `test_worker_env_is_allowlist` — recorder/stub исполнения фиксирует
  переданный `env`: нет `PYTEST_ADDOPTS`/`PYTHONPATH`/`PYTHONHOME`, PATH
  начинается с venv, TEMP указывает в staging (Windows).
- `test_env_override_token_rejected` — команды `pytest PYTEST_ADDOPTS=-x`,
  `python -m pytest FOO=bar` → ERROR, не исполняются.
- Обновить `test_allowed_shell_commands_still_run` — теперь работает через
  pinned-интерпретатор и проходит на любой машине (это и есть фикс
  независимого failure №1).

### Шаг 2 — Реализация

1. `InterpreterPolicy`/`ExecutionEnv` (в qualify.py или qualify_staging.py):
   - `resolve(argv) -> list[str]` — канонизация head по п.2.1;
   - `build_env() -> dict[str, str]` — allowlist по п.2.2;
   - платформенная сборка через `sys.platform`/`os.name`, без хардкода
     абсолютных путей (только вычисленные: staging root, venv, git dir
     из `shutil.which("git")` на judge-стороне).
2. `SandboxIO.shell`: `subprocess.run(resolve(argv), env=build_env(),
   cwd=work_dir, shell=False, timeout=...)`.
3. Парсер: токены с `=` (кроме разрешённых `--gate`-форм) → отказ с reason
   `env_override` (reason попадает в ToolEvent — нужно QF-006).
4. Убрать из `SandboxIO.shell` наследование окружения полностью; в тестах
   stub-исполнитель фиксирует env (не полагаться на реальный subprocess для
   env-ассертов).

### Шаг 3 — Регрессия

- Полный suite (особенно `test_allowed_shell_commands_still_run` — фикс
  дефекта из независимой проверки), оба smoke.
- Дважды проверить: время тестов не улетело (pinned-интерпретатор — это
  staging-venv из QF-004, session-fixture reuse).

## 4. Границы и запреты

- Не менять argv-контракт Worker'а (system prompt и `parse_shell_argv`
  принимают те же команды; канонизация — только на исполнении).
- Не использовать `sys.executable` runner'а напрямую для worker-команд:
  только staging-venv (в нём pytest есть всегда; runner-venv — деталь
  judge-окружения). Исключение — юнит-тесты без staging: там stub.
- Не добавлять переменные в allowlist «на всякий случай»: каждая — с
  тестом необходимости.

## 5. Acceptance

- [ ] PATH начинается с чужого Python без pytest — разрешённый тест всё
      равно использует pinned-интерпретатор (тест зелёный).
- [ ] Запрещённые env overrides отклоняются (argv-токены KEY=VALUE).
- [ ] Передаваемый env — allowlist; `PYTHON*`/`PYTEST_*` отсутствуют.
- [ ] Один и тот же argv-контракт проходит на Windows и POSIX (POSIX-ветки
      покрыты; не исполнимые на Windows — skip с обоснованием).
- [ ] Полный suite зелёный (включая починенный
      `test_allowed_shell_commands_still_run`), smoke зелёные.

## 6. Evidence для RESULT.md

1. Red-вывод новых тестов (и текущий failure независимой проверки как
   «до»).
2. Green-вывод полного suite: counts (0 failed), оба smoke rc=0.
3. Пример resolve() для `python -m pytest --version` на данной машине.

## 7. Commit

Один commit: `qualify: pin interpreter and environment`.
Состав: `scripts/qualify.py` (± `scripts/qualify_staging.py`),
`tests/unit/test_qualify.py`, `RESULT.md`.
