# QF-024 — результат исполнения

- **Статус:** выполнено
- **Базовый commit (parent):** `8f48271602d8a3620a15fc2248d640f3a5dde084`
  (QF-023); ветка `feature/2026-09-11-audit`
- **Итоговый commit:** тот, в котором лежит этот файл (child of base)
- **Инструменты:** Python 3.12.14 (.venv, CPython), pytest 9.1.1, Windows
  10.0.26200 (win32)
- **Red evidence:** `python scripts/result_integrity.py` на базовом commit —
  2 violations: (1) QF-017 RESULT ссылался на alternate base `6267f84`
  (commit существует, но НЕ в ancestry активной ветки — непопавшая в ветку
  редакция «assets: recover interrupted bundle transactions»); (2) durable
  wheel evidence в `bench/builds/` указывал на commit `141c2ae` (wave 1), а
  не на проверяемый commit wave 2; отдельного `RESULT.md` QF-018 не
  существовало.

## Реализация

- **`scripts/result_integrity.py`** (новый) — checker ссылочной целостности
  RESULT: каждый SHA-подобный токен в commit-строках обязан существовать
  (`cat-file -e`) и находиться в ancestry активной ветки
  (`merge-base --is-ancestor`); исторические неверные ссылки сохраняются
  только как явно размеченные correction-секции (заголовок
  «Коррекция/Correction») того же файла и исключаются из violations;
  `--expect` делает отсутствующий RESULT.md нарушением; хеши, помеченные
  `sha256:`/`digest:`, не считаются commit-ссылками.
- **Коррекция QF-017** (добавлена заметкой, история не переписывалась):
  неправильный base `6267f84` → фактический parent `6b44c66c26aa…` с
  объяснением alternate commit.
- **QF-018**: создан отдельный
  [RESULT.md](../QF-018-engineering-qualification/RESULT.md) со статусом
  `partial / not accepted`, точным перечнем выполненных проверок, skips и
  найденных дефектов.
- **Canonical line endings bundle (новый дефект, найден при пересборке
  evidence)**: `_generate` копировал working-tree байты — на CRLF-машине
  закоммиченный манифест хешировал CRLF-контент, тогда как canonical
  содержимое git (`.gitattributes: * text=auto eol=lf`) — LF: fresh
  checkout и wheel из него были неверифицируемы. `_copy_canonical`
  нормализует CRLF→LF для текстовых ассетов (бинарные не трогаются);
  bundle перегенерирован (45 assets, LF), `--check` — up to date.
- **Durable wheel evidence**: пересобран явно на чистом worktree текущего
  commit'а (содержит полный commit SHA, wheel sha256, build
  frontend/backend, python/platform, команды smoke; `bench/builds/…-build-manifest.json`,
  `--force`). Точный SHA commit'а записи — в манифесте и в RESULT QF-025
  (следующий release-коммит, куда evidence-файл и попадает — принятый в
  wave 2 паттерн: evidence для commit X коммитится позже).
- **Release report** переписан с разделением: historical evidence (волны
  1–2 с коррекциями), current engineering evidence (QF-019–QF-024), pending
  reference evidence (QF-012 — только LM Studio) + pending live-container
  прогоны (нет daemon на машине).

## Проверки

| # | Команда | Результат |
|---|---|---|
| 1 | `python scripts/result_integrity.py` (Red, до коррекций) | 2 violations (6267f84 not in ancestry; отсутствие механизма/expected) |
| 2 | `pytest tests/unit/test_result_integrity.py -q` | extraction/exemption/expect-матрица — зелёная |
| 3 | `python scripts/result_integrity.py --expect QF-018 … QF-024` | ok (после коррекций) |
| 4 | asset-сьют после LF-нормализации | 0 failed |

Дерево после commit: чистое по tracked-файлам.
