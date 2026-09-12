# QF-005 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `b3ed321` (QF-004)
- **Инструменты:** Python .venv 3.12.14 (uv), pytest, git 2.45.1, Windows 10.0.26200

## Реализация

- `StagingRoot.env()` — окружение собирается **с нуля** (allowlist, ничего не
  наследуется от judge-процесса): Windows — `PATH` (интерпретатор, git,
  System32), `SYSTEMROOT`, `SYSTEMDRIVE`, `COMSPEC`, `PATHEXT`,
  `TEMP`/`TMP` → `<staging>/tmp`; POSIX — `PATH=<venv bin>:/usr/bin:/bin`,
  `HOME=<staging>/home`, `TMPDIR=<staging>/tmp`. Никаких `PYTHON*`,
  `PYTEST_*`, `DELTAFUSE_*`, прокси и путей репозитория.
- Interpreter pin на границе исполнения (`SandboxIO.shell`): `python …` →
  `<pinned python> …`; `pytest …` → `<pinned python> -m pytest …`. argv-контракт
  Worker не изменён (парсер принимает те же команды). Pinned =
  `StagingRoot.interpreter()` (staging-venv при `build_venv=True`,
  иначе интерпретатор runner'а — см. отклонение QF-004).
- Парсер: argv-токен с `=`, не начинающийся с `-` → отказ `env_override`
  (закрывает `pytest PYTEST_ADDOPTS=-x`, `FOO=bar`); reason попадает в
  ToolEvent.

## Red-фаза (до реализации)

```
FAILED test_pytest_head_resolved_to_module      (pytest head шёл в PATH как есть)
FAILED test_worker_env_is_allowlist             (TEMP наследовался из окружения)
FAILED test_env_override_token_rejected         (KEY=VALUE проходил как positional)
```

`test_python_resolved_to_pinned_interpreter` был зелёным до реализации:
подстановка токена `python` сделана в QF-004 (зафиксировано там как
исполнение pinned-интерпретатора); тест оставлен как регрессия, включая
проверку, что враждебный `python` первым в PATH не запускается (POSIX-ветка
с маркером).

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests
414 passed, 1 skipped, 54 warnings in 173.67s   (0 failed)
```

`test_allowed_shell_commands_still_run` — зелёный (фикс независимого
failure №1). Smoke: ps1 rc=0, sh rc=0.

Пример `resolve()` на данной машине (`python -m pytest --version`):
```
['C:\\Users\\ghost\\workspace\\gste\\deltafuse\\.venv\\Scripts\\python.exe', '-m', 'pytest', '--version']
```
(путь вычисляется от `sys.executable` judge-процесса / staging-venv, не хардкод).

## Acceptance

- [x] Чужой Python первым в PATH не используется (pinned-интерпретатор).
- [x] Env overrides через argv отклоняются (`env_override`).
- [x] Передаваемый env — allowlist; `PYTHON*`/`PYTEST_*` отсутствуют;
      TEMP/HOME/TMPDIR в staging.
- [x] argv-контракт един для Windows и POSIX (платформенная ветка — только
      сборка env); POSIX-ветки покрыты гейтами `sys.platform`.
- [x] Полный suite 0 failed; оба smoke rc=0.
