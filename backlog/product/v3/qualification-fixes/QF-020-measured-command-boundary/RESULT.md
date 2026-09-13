# QF-020 — результат исполнения

- **Статус:** выполнено (код/тесты/документация); live adversarial-матрица в
  реальном runtime — не выполнена: docker CLI 29.7.2 есть, daemon не запущен
- **Базовый commit:** `fb446047bd41bf735f420acd5148733f23b7d19a` (QF-019)
- **Итоговый commit:** тот, в котором лежит этот файл (child of base)
- **Инструменты:** Python 3.12.14 (.venv, CPython), pytest 9.1.1, Windows
  10.0.26200 (win32)
- **Red evidence:** `tests/unit/test_qualify_boundary_policy.py` на базовом
  commit — 22/22 тестов падали: hardening-флагов старта не было, эффективная
  политика не измерялась (только declared), probe исполнялся в ОТДЕЛЬНОМ
  контейнере (не в command-контейнере Worker'а), sentinel искался только по
  host-пути (копия внутри разрешённого mount оставалась незамеченной —
  прежний ложный негатив), rootfs/control paths/scratch не проверялись,
  identity не сверялась, `.qual-*` scratch не исключался из unjournaled.

## Реализация

- **Единая политика command-контейнера** (`COMMAND_CONTAINER_POLICY`):
  `--network none` (LM Studio вызывает judge host — контейнеру сеть не
  нужна), `--read-only`, non-root `--user 1000:1000`, `--cap-drop ALL`,
  `--security-opt no-new-privileges`, `--memory 2g`, `--pids-limit 256`;
  `TMPDIR`/`HOME` направлены в gitignored scratch ВНУТРИ sandbox
  (`.qual-scratch`/`.qual-home`), запись возможна только в sandbox.
- **Измерение политики**: `inspect()`/`measure_policy()` снимают EFFECTIVE
  mounts, image digest, user, security options, network mode из runtime
  inspect; `verify_policy()` сверяет с ожидаемой политикой (лишний mount,
  root user, writable rootfs, сохранённая capability, bridge вместо none,
  memory/pids, drift image digest — каждое расхождение названо);
  `assert_policy_clean` блокирует run. Declared tag больше не attestation.
- **Probe в том же контейнере** (`BOUNDARY_PROBE_SCRIPT` v2 +
  `ContainerCommandExecutor.run_boundary_probe`): исполняется через `exec`
  в контейнере Worker-команд ДО первой и ПОСЛЕ последней команды; проверяет:
  sentinel недоступен по host-пути, не находится по уникальному имени и по
  точному content-hash (поиск по всем видимым корням — копия внутри
  разрешённого mount = LEAK); pack/checkout имена не находятся; записи вне
  sandbox/scratch невозможны; rootfs и runtime control paths
  (`/var/run/docker.sock`) не записываемы; сеть недоступна; scratch записываем
  (positive control); identity контейнера измерена изнутри (`/proc/self/cgroup`)
  и сверяется с container id сессии.
- **Runner** (`scripts/qualify.py`): старый pre-campaign probe в отдельном
  контейнере удалён; `run_case` isolated-ветка: scratch-каталоги →
  `measure_policy`+verify → probe(before) → `drive_worker` → probe(after),
  оба прогона в одном container id; отчёты политики и probe
  (`executor.probe_reports`) с provenance measured попадают в
  manifest-attestation после каждого прогона; утечка/расхождение →
  `BoundaryBlocked` (класс `boundary_error` в схемах report/manifest),
  кампания прерывается. `.qual-home/`, `.qual-scratch/` добавлены в
  GITIGNORE — scratch никогда не считается unjournaled change.
- **Threat model** обновлён: граница QF-019/QF-020 (argv-only crossing,
  wheel-only образ, digest-ссылка), единая измеряемая политика, probe
  before/after, исправленный sentinel-поиск; ограничение «bridge с
  host-gateway alias» удалено — сети у контейнера нет.

## Проверки

| # | Команда | Результат |
|---|---|---|
| 1 | `.venv/Scripts/python.exe -m pytest tests/unit/test_qualify_boundary_policy.py -q` (Red, на `fb44604`) | 22 failed — Red по каждому пункту инварианта |
| 2 | та же команда + QF-019/qualify-набор после реализации | 0 failed |
| 3 | `.venv/Scripts/python.exe -m pytest tests -q -p no:cacheprovider --junitxml=…` | tests=580, failures=0, errors=0, **skipped=7**, exit 0 (573 passed) |

Skips (7): 4 — переписанная live boundary-матрица QF-020
(`test_qualify_isolated_boundary.py`: measured policy, before/after в одном
контейнере, sentinel-in-mount, adversarial pytest), 2 — live command-container
QF-019, 1 — опциональный PBT. Skip не считается boundary-доказательством.

## Ограничения

- docker daemon недоступен на машине исполнения: live-матрица QF-020 (4
  теста) и live command-container smoke (2 теста QF-019) выполнены только
  как fake-runtime модели + cross-platform исполнение probe-скрипта;
  сохранённые Windows-host/POSIX-container прогоны требуются до QF-025.
- Механика cgroup-identity зависит от runtime; при отсутствии токена
  расхождение не заявляется, но сам факт исполнения probe и Worker-команд
  через один container id проверяется всегда.
- Дерево чистое после commit; tracked evidence не перезаписывался.
