# QF-018 — результат исполнения (восстановлен задним числом, QF-024)

- **Статус:** частично исполнено / НЕ принято (partial / not accepted)
- **Базовый commit:** `6b44c66c26aad1907aba9da49a5c79002a6c2c61` (QF-016)
- **Commit записи:** `01037cd` (release: record wave 2 engineering
  qualification (partial)) — полный SHA
  `01037cda2dc258985046fb146febc31d7a1d3cd3`; отдельного `RESULT.md` для QF-018 в момент исполнения НЕ
  существовало — этот файл восстановлен пакетом QF-024 по правилу 2.
- **Инструменты:** Python 3.12 venv, Windows 10.0.26200

## Что было выполнено (факты из release-report §0, commit `01037cd`)

1. Полный pytest: `534 passed, 6 skipped` (5 — live boundary-матрица QF-013
   без container daemon, 1 — опциональный PBT).
2. PowerShell smoke — passed; Git Bash/POSIX smoke (Git Bash) — passed.
3. Asset drift отсутствовал (`sync_assets.py --check`, 44 assets).
4. Wheel evidence сгенерирован явно — НО для commit `141c2ae…` (wave 1), а
   не для проверяемого commit wave 2: durable evidence отставал от кода
   (дефект зафиксирован wave 3).
5. Legacy runtime search — чисто (исторические упоминания только в
   документации/RESULT).

## Почему НЕ принято

Независимая приёмка wave 2 (основание —
[qualification-fix-plan-wave-3.md](../../qualification-fix-plan-wave-3.md))
подтвердила блокеры, снимающие статус `engineering-passed`:

- container entrypoint неисполним с заявленным wheel-only image:
  смонтированный `qualify.py` импортировал отсутствующие в wheel
  helper-модули (`ModuleNotFoundError` до Worker) — дефект QF-019;
- sentinel создавался ВНУТРИ разрешённого mount, probe проверял
  несуществующий host path; probe и Worker исполнялись с разными network
  policies — дефект QF-020;
- schema+semantic validation пропускали нарушающий T1–T8 отчёт с
  `verdict: pass` — дефект QF-021;
- токенизатор: численный допуск `+48` внесён без maintainer Decision —
  дефект QF-022;
- `__init__.py` asset bundle не был покрыт hash — дефект QF-023;
- durable wheel evidence указывал на commit `141c2ae`, RESULT QF-017 — на
  alternate base `6267f84`; отдельного RESULT QF-018 не было — дефект
  QF-024;
- live adversarial boundary-матрица и POSIX-прогоны не сохранены (нет
  container daemon на машине исполнения);
- QF-012 не запускался (нет reference LM Studio host) — остаётся
  `blocked`.

Итог: `engineering-failed / correction wave 3`; исправления —
[qualification-fix-plan-wave-3.md](../../qualification-fix-plan-wave-3.md),
повторная квалификация — QF-025.
