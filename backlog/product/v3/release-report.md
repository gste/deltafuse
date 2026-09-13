# DeltaFuse 3.0 — release qualification report

- **Статус:** `engineering-passed / reference-pending` (wave 3, QF-025; см. §0.3)
- **Пороги:** [thresholds.md](thresholds.md) (T1–T8, absolute)
- **Runner:** [scripts/qualify.py](../../../scripts/qualify.py)
- **Обновлён:** 2026-09-13 (независимая приёмка Wave 2; см.
  [qualification fix plan wave 3](qualification-fix-plan-wave-3.md))

## 0.1 Независимая приёмка Wave 2

Wave 2 не принята как завершённая. Подтверждены `534 passed, 6 skipped`, оба
smoke и Windows recovery, но найдены блокеры:

- container entrypoint не работает с заявленным wheel-only image: смонтированный
  `qualify.py` импортирует отсутствующие helper modules;
- sentinel находится внутри разрешённого mount, а probe и Worker используют
  разные network policies;
- schema+semantic validation пропускают нарушающий T1–T8 report с `verdict: pass`;
- tokenizer allowance `+48` внесён без требуемого maintainer Decision;
- `__init__.py` asset bundle не покрыт hash;
- durable wheel evidence относится к commit `141c2ae`, а не к Wave 2;
  QF-017 RESULT ссылается на alternate base SHA; отдельного QF-018 RESULT нет.

Исправления выполняются по
[qualification-fix-plan-wave-3.md](qualification-fix-plan-wave-3.md). До QF-025
статус остаётся engineering-failed; QF-012 не запускается.


## 0.2 Классы evidence (QF-024)

Отчёт различает три класса; смешение классов запрещено:

1. **Historical evidence** — записи волн 1–2 (§3, §3.1, §0) и RESULT
   QF-001–QF-018. Сохраняются как история с явными коррекциями
   (QF-017: alternate base `6267f84` → фактический parent `6b44c66`;
   отдельный [RESULT QF-018](qualification-fixes/QF-018-engineering-qualification/RESULT.md)
   — `partial / not accepted`). Release-доказательством не являются.
2. **Current engineering evidence** — QF-019–QF-024
   ([qualification-fixes/](qualification-fixes/README.md)): исполнимый
   command executor, измеряемая граница (probe той же среды, network none,
   hardened), независимый disk-пересчёт T1–T8, threshold governance,
   полное hash-покрытие bundle, восстановленный provenance. Проверено
   тестами на Windows-host; live-container прогоны — pending (нет daemon).
3. **Pending reference evidence** — QF-012 (девять живых прогонов на
   `ornith-1.5-35b-a3b`): блокирован ТОЛЬКО доступностью LM Studio host;
   инженерных блокеров после QF-025 не остаётся.

Durable wheel evidence пересобран на commit wave 3 (см. RESULT QF-024);
stale-запись `141c2ae` заменена. Целостность ссылок RESULT проверяется
`python scripts/result_integrity.py`.

## 0. Wave 2 engineering qualification (QF-018, частично исполнена)

Выполнено на ветке `feature/2026-09-11-audit` (Windows 10.0.26200, Python
3.12 venv):

- полный pytest: `534 passed, 6 skipped` — каждый skip обоснован: 5 —
  adversarial boundary-матрица QF-013 требует недоступного на машине
  container runtime (`DELTAFUSE_QUAL_IMAGE` + docker daemon), 1 —
  отсутствие локального PBT runner; boundary-матрица обязана быть
  сохранена до `engineering-passed`;
- PowerShell smoke: passed (включая [4/4] re-validate product layout);
- Git Bash/POSIX smoke: passed; asset drift отсутствует
  (`sync_assets.py --check`: 44 assets, up to date);
- wheel evidence сгенерирован явно (`scripts/wheel_evidence.py`);
- legacy runtime search: `chars-div-4-fallback` остался только в истории
  (RESULT/тест-документация); `docs/init`/`docs/todo` присутствуют лишь в
  `LEGACY_FORBIDDEN_PATHS` валидатора.

**Не выполнено (блокирует `engineering-passed`):**

- QF-013 adversarial run внутри фактической isolated boundary (нет
  docker/podman daemon + qual image на машине исполнения); hard-kill
  матрица QF-016 подтверждена только на Windows;
- POSIX/container результаты boundary-матрицы;
- QF-012 (девять живых прогонов) — блокирован недоступностью reference
  LM Studio host, остаётся `blocked`.

## 1. Референсная конфигурация

| Параметр | Значение |
|---|---|
| Модель Worker | `ornith-1.5-35b-a3b` (локальная, 35B A3B) |
| Host | LM Studio, OpenAI-совместимый endpoint, context limit 32768 |
| Cloud/mock fallback | запрещён карточкой DF3-009 |
| Framework pin | фиксируется `scripts/qualify.py` на момент прогона |

## 2. Прогоны (по три чистых прогона на case)

Каждый прогон публикуется как disk report в `bench/runs/<campaign>/<run_id>/report.yaml`
(формат — [thresholds.md](thresholds.md)). **Все** прогоны каждого case приводятся;
выбор лучшего прогона запрещён.

| Case | Run 1 | Run 2 | Run 3 | Медиана correctness | Медиана process | Verdict |
|---|---|---|---|---|---|---|
| M01-cooldown | _pending_ | _pending_ | _pending_ | — | — | pending |
| M02-policy-stats | _pending_ | _pending_ | _pending_ | — | — | pending |
| M03-adversarial | _pending_ | _pending_ | _pending_ | — | — | pending |

**Прогоны ещё не выполнялись.** Сначала требуется закрыть QF-013–QF-018 из
[qualification fix plan wave 2](qualification-fix-plan-wave-2.md);
референсный host с моделью также недоступен на машине разработки. Данные
заполняются только фактическими результатами.

## 3. Независимая инженерная перепроверка без модели (2026-09-12)

Заявленная квалификация выполнялась на commit
`25551473ad4c07a4c5b1e2fabdd782792f7e6975`. Независимая перепроверка выполнена
на commit `c12803d` ветки `feature/2026-09-11-audit` после заявленных
исправлений:

1. Полный pytest-сьют в независимом окружении: **1 failed, 382 passed,
   1 skipped**. Failure:
   `tests/unit/test_qualify.py::test_allowed_shell_commands_still_run` — команда
   `python -m pytest --version` выбрала Python без pytest.
2. `tests/smoke-test.ps1` — rc 0.
3. `tests/smoke-test.sh` (Git Bash) — rc 0.
4. Default wheel smoke перезаписывает tracked build manifest: версия Python и
   wheel hash меняются. Изменение после проверки было откатано; тест не
   удовлетворяет требованию чистого дерева.
5. Layout validation чистого v3-продукта (sh-валидатор) — rc 0.
6. Поиск legacy runtime paths: остались только намеренные negative-фикстуры
   (`schema_version: 2` в тестах fail-closed); bench seed catalogs переведены
   на v3.

Дополнительные блокеры подтверждены прямыми probes: пустой envelope разрешает
запись `src/evil.py`; `git diff --output=leak.txt` проходит parser; T5 сообщает
`unique_files: 0` после реального чтения файла. Asset replacement остаётся
неатомарным, T8 проходит без обязательного defense evidence, а host fallback и
tokenizer provenance не измеряются полностью.

**Инженерный блокер не снят.** Исправления перечислены в
[qualification-fix-plan.md](qualification-fix-plan.md). Кампания
`scripts/qualify.py` не принимается для reference qualification до выполнения
QF-001–QF-011; отсутствие LM Studio отдельно блокирует QF-012.

## 3.1 Инженерная переквалификация после QF-001–QF-010 (2026-09-12)

Все 10 fix-пакетов выполнены отдельными коммитами на ветке
`feature/2026-09-11-audit`. Переквалификация выполнена на чистом commit
`141c2ae92fdf1ae8689a795a36a83490f19c1688` (рабочее дерево чистое до и после,
кроме явно сгенерированного wheel evidence). В ходе переквалификации
обнаружены и исправлены двумя fix-коммитами два дефекта wheel-install пути:

- `4b17138` installer: forward bundle skills dir in wheel installs —
  wheel-установка оставляла adapter roots пустыми, `deltafuse validate-layout`
  падал с 24 missing-skill ошибками;
- `141c2ae` installer: write generated skills with LF endings — CRLF ломал
  PowerShell-валидатор (`$`-якорь не совпадает перед `\r\n`).

Окружение: Python 3.12.14 (CPython, uv venv), pip 26.2.1 (venv сборки:
25.0.1), git 2.45.1.windows.1, Windows 11 10.0.26200 (platform:
`Windows-11-10.0.26200-SP0`).

| # | Проверка | Команда | Результат |
|---|---|---|---|
| 1 | Полный pytest-сьют | `.venv/Scripts/python.exe -m pytest tests` | **449 passed, 0 failed, 1 skipped** (~283s). Skip: `tests/unit/test_spec_style.py::test_optional_pbt_skips_without_local_runner` — RM-031: PBT опционален, Hypothesis не установлен |
| 2 | PowerShell smoke | `pwsh -File tests/smoke-test.ps1` | rc 0 |
| 3 | POSIX smoke (Git Bash) | `bash tests/smoke-test.sh` | rc 0 |
| 4 | Wheel smoke | `pytest tests/integration/test_wheel_smoke.py` | 2 passed; `git status --porcelain` до/после идентичен (QF-010 acceptance) |
| 5 | Wheel release evidence | `python scripts/wheel_evidence.py --output-dir bench/builds --force` | rc 0; commit `141c2ae…`, wheel sha256 `bad5ada3…`, pip wheel 25.0.1, setuptools 84.0.0 |
| 6 | Layout validation свежего v3-продукта | wheel `deltafuse init` (tmp) + `deltafuse validate-layout` / `validate-config` / `tests/validate-layout.sh` / `tests/validate-layout.ps1` | все rc 0 |
| 7 | Legacy runtime paths | `git grep -nE "docs/(init\|todo)/\|schema_version: *2\|compat" -- src scripts process docs` | только intentional: отрицательные формулировки в docs/README, using, bench-кейсы backward-compat (требования кейсов, не adapters) |
| 8 | Asset bundle drift | `python scripts/sync_assets.py --check` | rc 0 (44 assets) |

POSIX-платформенная ветка (native Linux/`validate-layout.sh` под Linux)
выполнена через Git Bash; отдельная Linux-машина недоступна — native-прогон
не выполнен (не блокер, зафиксировано).

Зелёный suite подтверждён, но независимая приёмка обнаружила не покрытые им
контрактные дефекты: отсутствие обязательной OS-изоляции Worker, неточный T2,
не fail-closed tokenizer fallback, небезопасное crash recovery assets и
неполную schema disk artifacts. Поэтому инженерный статус снова `failed` до
выполнения QF-013–QF-018. Reference runs QF-012 после этого по-прежнему требуют
LM Studio с `ornith-1.5-35b-a3b`.

## 4. Критерии закрытия DF3-009

1. Три чистых прогона каждого case выполнены на референсном host.
2. Каждый отчёт прогона и медианы удовлетворяют T1–T8.
3. `verdict: pass` по всем трём cases → карточка закрывается, v3.0.0 release.

## 0.3 Wave 3 engineering qualification (QF-025, 2026-09-13)

Выполнена на commit `082e6f429a0a4e16f4f1cb5f90ff71b7ac385bc9` ветки
`feature/2026-09-11-audit` (Windows 10.0.26200, Python 3.12.14, docker
29.7.2). Полный отчёт —
[QF-025 RESULT](qualification-fixes/QF-025-wave3-engineering-qualification/RESULT.md).

- Полный pytest: **644 passed, 0 failed, 1 skipped** (только опциональный
  PBT). Все 6 live-тестов command-контейнера и adversarial границы
  исполнены в реальном runtime (docker Linux engine); skip больше не
  покрывает инженерные гарантии.
- Live boundary: image `sha256:84c28058…` (build manifest в `bench/builds/`,
  commit `082e6f4…`), network none, read-only rootfs, non-root 1000:1000,
  cap-drop ALL, no-new-privileges, memory/pids limits, sandbox+tmpfs
  scratch; probe before/after в одном container id с Worker-командами.
- QF-021 mutation matrix, QF-022 governance checker, QF-023 asset/hard-kill
  матрицы — зелёные; PowerShell/POSIX smoke, wheel smoke, 4 layout
  validators на продукте из свежего wheel — rc 0; asset drift отсутствует;
  result integrity ok.
- Durable evidence: wheel manifest + qual-image manifest на commit
  `082e6f4…` (`bench/builds/`).

**QF-012** остаётся `blocked` ТОЛЬКО доступностью reference LM Studio host
(`ornith-1.5-35b-a3b`, context 32768). Нативный POSIX-host прогон недоступен
(нет второй машины); POSIX-среда команд/probe — сам Debian-контейнер.
