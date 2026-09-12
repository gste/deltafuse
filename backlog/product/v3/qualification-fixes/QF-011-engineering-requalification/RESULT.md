# QF-011 — результат исполнения (инженерная переквалификация)

- **Статус:** выполнено; статус программы: `engineering-failed` →
  `engineering-passed / pending reference runs`
- **Commit переквалификации:** `141c2ae92fdf1ae8689a795a36a83490f19c1688`
  (после fix-коммитов `4b17138`, `141c2ae`, см. «Findings»)
- **Окружение:** Python 3.12.14 (CPython, uv venv), pip 26.2.1 (build venv
  pip 25.0.1), git 2.45.1.windows.1, Windows 11 10.0.26200,
  platform `Windows-11-10.0.26200-SP0`
- **Дерево:** `git status --porcelain` пуст до начала; после набора — только
  свежий `bench/builds/deltafuse-3.0.0-py3-none-any-build-manifest.json`
  (единственное допустимое tracked-изменение, вошло в commit)

## Проверки

| # | Проверка | Команда | rc | Counts | Время |
|---|---|---|---|---|---|
| 1 | Полный pytest | `python -m pytest tests` | 0 | **449 passed, 0 failed, 1 skipped** | 283s |
| 2 | PowerShell smoke | `pwsh -File tests/smoke-test.ps1` | 0 | — | ~60s |
| 3 | POSIX smoke | `bash tests/smoke-test.sh` | 0 | — | ~60s |
| 4 | Wheel smoke | `pytest tests/integration/test_wheel_smoke.py` | 0 | 2 passed | ~120s |
| 5 | Wheel release evidence | `python scripts/wheel_evidence.py --output-dir bench/builds --force` | 0 | commit `141c2ae…`, sha256 `bad5ada3…`, pip wheel 25.0.1, setuptools 84.0.0 | ~90s |
| 6 | Layout validation чистого v3-продукта | wheel `deltafuse init` (tmp) → `deltafuse validate-layout`, `deltafuse validate-config`, `tests/validate-layout.sh`, `tests/validate-layout.ps1` | 0/0/0/0 | — | — |
| 7 | Legacy search | `git grep -nE "docs/(init\|todo)/\|schema_version: *2\|compat" -- src scripts process docs` | 0 находок-дефектов | только intentional (см. ниже) | — |
| 8 | Asset drift | `python scripts/sync_assets.py --check` | 0 | 44 assets | — |

- Единственный skip: `test_optional_pbt_skips_without_local_runner`
  (RM-031/KI-07: Hypothesis не установлен — skip, не gate fail).
- Дерево до/после wheel smoke (п.4): байт-в-байт идентичное (`diff` пуст).
- Legacy findings классификация: `docs/README*`, `docs/using*` — явные
  negative-утверждения («installer не создаёт docs/init, docs/todo»);
  `docs/bench.ru.md`, `process/bench/cases/*` — backward compatibility как
  требования bench-кейсов (не compatibility adapters); `docs/contracts/*` —
  заявленный compatibility-контракт инструментов. `schema_version: 2` в
  src/scripts отсутствует.

## Findings и fix-коммиты

Переквалификация выявила два дефекта wheel-install пути; каждый исправлен
отдельным fix-коммитом с Red-тестом, после чего проверка 6 повторена с
чистого commit (перегенерация wheel → свежая установка → все 4 валидатора):

1. `4b17138` **installer: forward bundle skills dir in wheel installs** —
   `installer.install()` вычислял `skills_dir` для bundle-режима, но не
   передавал его в `install_adapter_skills`; продукт из wheel получал пустые
   adapter roots, `deltafuse validate-layout` падал (24 ошибки
   missing-skill). Red: `tests/unit/test_installer_skills_dir.py`.
2. `141c2ae` **installer: write generated skills with LF endings** —
   `write_text` на Windows писал CRLF; PowerShell-валидатор
   (`'^# DO NOT EDIT…$'`) не совпадал перед `\r\n`. Red-фиксация —
   фактический rc=1 `validate-layout.ps1` на wheel-продукте до фикса.

Также при генерации release evidence (`build_backend` пуст из-за отсутствия
setuptools в свежих venv) — `59b37da`, `787d630`: версия backend измеряется
из `Generator:` поля WHEEL-метаданных собранного wheel.

## Acceptance

- [x] Все обязательные проверки зелёные, точные counts сохранены.
- [x] Skip/невыполненные платформенные проверки обоснованы (native Linux
      недоступен; POSIX-ветка покрыта Git Bash — зафиксировано в release
      report §3.1).
- [x] Дерево до/после чистое, кроме wheel evidence, вошедшего в commit.
- [x] Release report содержит точные counts и SHA; статус обновлён.
- [x] DF3-009 остаётся `blocked` со ссылкой на QF-012.
