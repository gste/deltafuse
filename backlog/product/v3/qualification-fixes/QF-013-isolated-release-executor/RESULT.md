# QF-013 — результат исполнения

- **Статус:** выполнено (код/тесты/документация); live boundary-прогоны —
  отложены до QF-018 на машине с доступным container runtime
- **Базовый commit:** `3a8da0d` (wave 2 backlog)
- **Инструменты:** Python .venv 3.12, pytest, Windows 10.0.26200
- **Red evidence:** `tests/unit/test_qualify_executor.py`,
  `tests/integration/test_qualify_isolated_boundary.py` — сначала падали
  (`ModuleNotFoundError: qualify_executor`, fail-open default), затем зелёные.

## Реализация

- **`scripts/qualify_executor.py`** (новый): режимы исполнителя
  - `isolated` — обязателен для release/reference: Worker-фаза исполняется
    в контейнере (docker/podman auto-detect, image из
    `DELTAFUSE_QUAL_IMAGE`); монтируются только run sandbox (rw) и сам
    runner-скрипт (ro); judge pack и framework checkout не монтируются.
  - `local-dev` — только разработка: in-process runner с L1 staging; итоговый
    verdict кампании жёстко ограничен `non-release`
    (`apply_executor_verdict_cap`), release manifest с `pass` невозможен.
- **Adversarial boundary probe** (`boundary_probe` + `assert_boundary_clean`)
  исполняется ВНУТРИ фактической границы (контейнер с `--network none`,
  embedded probe-скрипт): чтение judge-sentinel по абсолютному пути, поиск
  `cases`/`hidden_suite`/`oracle` по mount roots, записи за пределами
  sandbox (host temp/home/checkout), сетевое соединение. Любая утечка →
  `BoundaryViolation`, кампания `PENDING` (exit 2) без Worker-вызовов.
- **Runner** (`scripts/qualify.py`): `--executor` с fail-closed default
  `isolated`; gate executor'а до host probe и до первого Worker-вызова;
  internal `--boundary-run` режим, исполняемый внутри контейнера
  (Worker-фаза пишет `.qual-metrics.json` в sandbox, judge сканирует и
  удаляет до scoring); manifest получил attestation-блок `executor`
  (kind/boundary/network_policy/runtime/image/mounts + probe-отчёт, все
  поля с provenance QF-007).
- **Схема** `run-manifest.schema.json`: `executor` обязателен (`$defs/attested`),
  verdict enum дополнен `non-release`.
- **Threat model** переписан: утверждение «доступ Worker-кода к host FS
  приемлем для release qualification» удалено как ошибочное; L1 помечен
  local-dev helper'ом, release-границей является только isolated executor.

## Проверки

- `pytest tests/unit/test_qualify*.py tests/integration/test_qualify_*.py`:
  84 passed, 5 skipped; полный suite: см. QF-018.
- Ограничение: на данной машине docker CLI есть, daemon не запущен →
  интеграционная boundary-матрица (5 тестов) SKIP. Skip не считается
  boundary-доказательством: QF-018 требует сохранённого прогона матрицы на
  Windows host и на выбранном POSIX/container runtime.
- Ограничение сети Worker-контейнера только LM Studio endpoint: bridge + host-gateway
  alias; runtime-level egress allowlist требует image/firewall-настройки и
  проверяется в QF-018 (зафиксировано в threat model как ограничение).
