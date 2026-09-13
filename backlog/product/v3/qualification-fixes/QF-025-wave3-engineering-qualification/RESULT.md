# QF-025 — результат исполнения: повторная инженерная квалификация Wave 3

- **Статус:** выполнено — `engineering-passed` (wave 3); QF-012 остаётся
  `blocked` ТОЛЬКО доступностью reference LM Studio host
- **Базовый commit (parent):** `082e6f429a0a4e16f4f1cb5f90ff71b7ac385bc9` (QF-024)
- **Итоговый commit:** тот, в котором лежит этот файл (child of base)
- **Платформа:** Windows 10.0.26200 (win32 host), Python 3.12.14 (.venv,
  CPython), pytest 9.1.1, docker 29.7.2 (Linux engine, Debian bookworm
  container = POSIX runtime для command-контейнера)

## Обязательные проверки

| # | Проверка | Команда / артефакт | Результат |
|---|---|---|---|
| 1 | Полный pytest, skip не покрывает QF-019–QF-024 | `pytest tests -q --junitxml` c `DELTAFUSE_QUAL_IMAGE` | **644 tests, 0 failed, 0 errors, 1 skipped** (только опциональный PBT), exit 0; все 6 live-тестов QF-019/QF-020 исполнены, не skip |
| 2 | Live command-container smoke (Windows host) | `tests/integration/test_qual_command_container.py` | 2 passed: `git --version`, `pytest --version`, `deltafuse --help` в контейнере; `/opt/qualify.py` отсутствует, `/sandbox` смонтирован |
| 3 | Полная QF-020 adversarial матрица без skip | `tests/integration/test_qualify_isolated_boundary.py` | 4 passed в реальном runtime: measured policy, before/after probe в одном container id, sentinel-in-mount = LEAK, adversarial Worker-pytest заблокирован |
| 4 | QF-021 disk mutation matrix + re-evaluation | `tests/unit/test_qualify_evidence.py` (38 тестов) + `semantic_validate_manifest` | зелёные: каждый мутант отклонён, runtime verdict воспроизводится из disk |
| 5 | QF-022 threshold governance checker | `scripts/threshold_governance.py` через `assert_threshold_governance` | `approved`; мутация thresholds / draft-Decision блокируются тестами |
| 6 | QF-023 asset mutation + hard-kill matrix | `test_sync_assets_hash_coverage.py` + `test_sync_assets_recovery.py` | зелёные на Windows (POSIX-ветка recovery — тот же код через lstat/islink; нативная Linux-машина недоступна — зафиксировано) |
| 7 | PowerShell smoke / POSIX smoke / wheel smoke / 4 layout validators | `tests/smoke-test.ps1`, `tests/smoke-test.sh` (Git Bash), `test_wheel_smoke.py`, `validate-layout{,.sh,.ps1}` + `validate-config` на продукте из свежего wheel | все rc 0 |
| 8 | Explicit wheel/image evidence на проверенном commit | `bench/builds/deltafuse-3.0.0-py3-none-any-build-manifest.json` (commit `082e6f4…`, wheel sha256 `60872ca8…`); `bench/builds/qual-image-3.0.0-082e6f42-manifest.json` (image digest `sha256:84c28058…`, wheel sha256, pinned base `python:3.12-slim-bookworm`, pytest 9.1.1) | записаны, schema-valid |
| 9 | Asset drift / legacy search / чистота дерева | `sync_assets.py --check` → up to date (45 assets); legacy search — только намеренные негативные формулировки; дерево после commit чисто по tracked-файлам | ok |

## Measured boundary report (live, Windows host → Linux container)

- image digest: `sha256:84c28058d38e80af6e0dccd2171a4b4add221238e2a7dd902e04c6680d8d8429`
  (config digest, measured `image inspect --format {{.Id}}`; build manifest
  согласован, commit `082e6f4…`)
- policy (runtime inspect, каждый run): `network_mode=none`,
  `ReadonlyRootfs=true`, `User=1000:1000` (non-root), `CapDrop=[ALL]`,
  `SecurityOpt=[no-new-privileges]`, `Memory=2147483648`, `PidsLimit=256`,
  mounts: ровно один rw bind `/sandbox` + tmpfs scratch/home ВНУТРИ
  sandbox-path (`/sandbox/.qual-scratch`, `/sandbox/.qual-home`)
- probe before/after: исполнен в ТОМ ЖЕ container id, что и Worker-команды
  (exec `-i`, identity из `/proc/self/cgroup` сверяется, где runtime её
  отдаёт); sentinel: host-path read blocked + поиск по имени и точному
  content-hash по всем корням — пусто; pack/checkout не находятся; записи
  вне sandbox/tmpfs невозможны; rootfs и `/var/run/docker.sock` не
  записываемы/отсутствуют; network blocked; scratch positive control ok.

## Live-run исправления (найдены настоящей квалификацией, judge-side)

- `exec -i` для probe (stdin targets): без него реальный runtime не
  передаёт stdin — живой прогон поймал то, что fake runtime моделировал
  не полностью;
- `search_roots=["/"]` вместо `os.sep` (judge host Windows давал `\`);
- scratch/home переведены на tmpfs внутри sandbox-path: Windows bind mount
  не поддерживает truncate/seek-паттерны pytest capture; whitelist в
  `verify_policy` (tmpfs обязателен, bind scratch = mismatch).

## Ограничения / статусы

- Нативный POSIX-host прогон недоступен (нет второй машины); POSIX-среда
  исполнения команды/probe — сам контейнер (Debian bookworm). Зафиксировано.
- Параллельная работа в том же репо: незакоммиченные файлы
  `backlog/product/v3/document-flow-benchmark/**` и модификация
  `process/bench/cases/M03-adversarial/oracle.yaml` принадлежат другому
  процессу исполнения, в этот commit не включены (полный suite с ними
  зелёный).
- **QF-012** остаётся `blocked` только по LM Studio host с
  `ornith-1.5-35b-a3b` (context 32768): 3×M01, 3×M02, 3×M03, T1–T8 на
  каждый отчёт и медианы — по [qualification-fix-plan-wave-3.md](../../qualification-fix-plan-wave-3.md)
  § «После Wave 3».
