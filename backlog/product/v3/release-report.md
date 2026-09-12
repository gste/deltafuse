# DeltaFuse 3.0 — release qualification report

- **Статус:** `engineering-pending / wave 2 implemented (QF-013–QF-017);
  boundary qualification blocked on isolated executor availability`
- **Пороги:** [thresholds.md](thresholds.md) (T1–T8, absolute)
- **Runner:** [scripts/qualify.py](../../../scripts/qualify.py)
- **Обновлён:** 2026-09-13 (wave 2: QF-013–QF-017 исполнены; см.
  [qualification fix plan wave 2](qualification-fix-plan-wave-2.md))

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
