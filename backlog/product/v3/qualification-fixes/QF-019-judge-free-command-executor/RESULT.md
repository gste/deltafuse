# QF-019 — результат исполнения

- **Статус:** выполнено (код/тесты/документация); live-прогоны в контейнере —
  не выполнены: docker CLI 29.7.2 есть, daemon не запущен (см. Ограничения)
- **Базовый commit:** `1f54049eda5c23aa54bf4da32b51eb893a89f64b` (wave 3 backlog)
- **Итоговый commit:** тот, в котором лежит этот файл (child of base)
- **Инструменты:** Python 3.12.14 (.venv, CPython), pytest 9.1.1, Windows
  10.0.26200 (win32)
- **Red evidence:** `tests/unit/test_qualify_command_executor.py` на базовом
  commit — коллекция падала `ImportError: cannot import name 'CommandResult'
  from 'qualify_executor'`: интерфейса CommandExecutor не существовало,
  release-shell исполнялся локальным `subprocess.run` из `SandboxIO`, а
  «isolated» Worker-фаза монтировала `qualify.py` в wheel-only image, где
  `import qualify_executor`/`qualify_semantic` давали `ModuleNotFoundError`
  до первого Worker-вызова.

## Реализация

- **`scripts/qualify_executor.py`**:
  - `CommandResult(kind, exit_code, stdout, stderr, detail)` — классификация
    исхода команды: `ok | exit | timeout | spawn_error | container_error`;
    не-UTF-8 вывод заменяется и помечается (`malformed output bytes replaced`);
    exit 125/126/127 с runtime-текстом ошибки классифицируется как
    `container_error`, а не как результат guest-команды;
  - `ContainerCommandExecutor` — персистентный command-контейнер на прогон:
    `run -d --rm --network none -v <sandbox>:/sandbox -w /sandbox <image>
    sleep infinity`; `run(argv, cwd, timeout)` передаёт уже разобранный argv
    в `exec` и возвращает `CommandResult`; `cwd` не равный смонтированному
    sandbox отклоняется; `stop()` завершает контейнер;
  - `LocalCommandExecutor` — direct-subprocess исполнитель для local-dev с
    канонизацией `python`/`pytest` на pinned interpreter (QF-005);
  - `IsolatedExecutor`: `release_ready` — только immutable digest-ссылка
    (`sha256:…`); `inspect_image_id()` — измеренный digest через
    `image inspect --format {{.Id}}`; `command_session(sandbox)`; `attest()`
    добавил `image_digest` (provenance measured) и `wheel_sha256`
    (derived из build manifest); расхождение digest манифеста и runtime →
    `ExecutorError`;
  - `resolve_executor("isolated")` требует digest-ссылку: тег без digest
    больше не принимается для release (PENDING с инструкцией собрать образ
    `scripts/build_qual_image.py`).
- **`scripts/qualify.py`**:
  - `SandboxIO(root, release_mode=…)` + `command_executor`: shell-команды
    идут через `CommandExecutor.run`; в release mode без исполнителя любая
    команда БЛОКИРУЕТСЯ и журналируется (`rejected: release mode requires an
    isolated command executor`), локальный `subprocess.run` недостижим;
    инвентарь/escape-walker/exit-4→T6-классификация сохранены для обоих
    путей (`_finish_shell` общий);
  - `drive_worker(..., command_executor=, release_mode=)` — Worker-фаза
    (model calls, orchestration) остаётся judge-side; за границу уходит
    только разрешённый argv;
  - `run_case` isolated-ветка: `executor.command_session(sandbox)` на прогон,
    `drive_worker(release_mode=True)`, `session.stop()` в `finally`;
    local-dev-ветка использует `LocalCommandExecutor(staging)`;
  - удалены неисполнимые `_run_worker_in_boundary`, `--boundary-run`,
    `--sandbox/--base-url/--model/--case`: смонтированный `qualify.py`
    импортировал отсутствующие в wheel helper-модули — заявленная
    конфигурация не могла стартовать.
- **`scripts/Containerfile.qual`** (канонический) + **`scripts/build_qual_image.py`**:
  wheel строится ПЕРВЫМ из чистого commit; контекст сборки содержит ТОЛЬКО
  wheel (+ pinned `BASE_IMAGE`, `PYTEST_PIN`, git); digest измеряется
  runtime-inspect; schema-валидированный манифест
  `bench/builds/qual-image-<version>-<commit8>-manifest.json`
  (`scripts/schemas/qual-image.schema.json`), атомарная запись, `--force`;
  печатает digest-ссылку для `DELTAFUSE_QUAL_IMAGE`. Тег без digest для
  release не принимается.
- **`run-manifest.schema.json`**: executor-блок дополнен `image_digest`,
  `wheel_sha256` (attested).

## Проверки

| # | Команда | Результат |
|---|---|---|
| 1 | `.venv/Scripts/python.exe -m pytest tests/unit/test_qualify_command_executor.py -q` (Red, на базовом commit) | collection ImportError (`CommandResult`) — Red подтверждён по исправляемому инварианту |
| 2 | та же команда после реализации | 16 passed, exit 0 |
| 3 | `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --junitxml=…` | tests=558, failures=0, errors=0, **skipped=8**, exit 0 (550 passed) |

Skips (8): 5 — live boundary-матрица QF-013, 2 — новые live command-container
проверки QF-019 (`tests/integration/test_qual_command_container.py`), 1 —
опциональный PBT. Skip не считается release-доказательством: live-прогоны
сохраняются до QF-025.

## Ограничения

- docker daemon на машине исполнения не запущен → live-сборка образа
  `build_qual_image.py` и live-smoke command-контейнера не выполнялись;
  контракт образа покрыт: static-тестом Containerfile (wheel-only, без
  judge-поверхности), fake-runtime моделированием run/exec/inspect и
  существующим wheel smoke (чистый venv из wheel). Durable image evidence
  с измеренным digest создаётся явно при доступном daemon (не позже QF-024/QF-025).
- Дерево чистое после commit; tracked evidence не перезаписывался.
