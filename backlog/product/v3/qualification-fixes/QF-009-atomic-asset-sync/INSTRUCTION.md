# QF-009 — атомарная синхронизация assets

- **Приоритет:** P1
- **Зависимости:** нет (независим от qualify-пакетов; можно выполнять
  параллельно с P0-очередью)
- **Commit:** `assets: make bundle replacement atomic`
- **Исходный дефект:** [qualification-fix-plan.md, QF-009](../../qualification-fix-plan.md)
- **Код на момент написания:** commit `bb02820`

Исполнитель: читай [README.md](../README.md) до начала работы.

## 1. Дефект

`scripts/sync_assets.py::sync()` удаляет целевой bundle ДО генерации
нового:

```python
# scripts/sync_assets.py:62-78 (bb02820)
def sync() -> list[str]:
    problems: list[str] = []
    if ASSETS.exists():
        shutil.rmtree(ASSETS)        # bundle исчез
    files, problems = _generate(ASSETS)   # генерация по месту
    ...
```

Между `rmtree` и завершением `_generate` bundle частичен или отсутствует.
Сбой генерации (исключение, переполнение диска, Ctrl-C) оставляет дерево
без `src/deltafuse/assets` — это не атомарная замена, и это противоречит
заявлению «неуспешная генерация никогда не оставляет отсутствующий или
частичный bundle» (release report, независимая проверка №3).

`--check` (V3-FIX-022) корректен и read-only; его не трогаем (только
переиспользуем проверку манифеста).

## 2. Нормативное поведение

1. Генерация идёт во **временном sibling-каталоге**
   `src/deltafuse/assets.next-<pid>-<rand>` (тот же том — для rename).
2. После генерации — самопроверка сгенерированного: manifest читается,
   каждый файл из manifest существует на месте и hash совпадает; проблемы
   канонических источников (`process/**` отсутствует и т.п.) — фейл ДО
   swap.
3. Атомарный swap с rollback (rename каталогов; `os.replace` не работает
   на непустых каталогах Windows):
   1. `assets` → `assets.prev-<pid>` (если существует);
   2. `assets.next-…` → `assets`;
   3. при неудаче шага 2 — откат `assets.prev-…` → `assets`;
   4. успех: `shutil.rmtree(assets.prev-…)`.
   Любая неудача на любом шаге оставляет предыдущий bundle байт-в-байт.
4. `--check` дополнительно остаётся read-only (уже так) и продолжает
   сверять: canonical source ↔ manifest ↔ packaged files.
5. Служебные каталоги (`*.next-*`, `*.prev-*`) при старте sync подчищаются
   (забытые после крэша), НИКОГДА не становятся просто переименованными в
   `assets` без самопроверки.

## 3. План работ

### Шаг 1 — Red-тесты (новый `tests/unit/test_sync_assets.py`)

- `test_failed_generation_keeps_previous_bundle` — fault injection:
  monkeypatch `_generate` так, чтобы он записал часть файлов и бросил
  исключение; вызвать `sync()` (в изолированной копии структуры:
  monkeypatch `ASSETS`/`REPO` на tmp-копию `process/` + `src/deltafuse/
  assets`); предыдущий bundle байт-в-байт идентичен (сравнить список
  путей + sha256 каждого файла до/после), мусор `*.next-*` вычищен.
- `test_swap_rollback_on_rename_failure` — инжект отказа на шаге rename 2
  (monkeypatch `Path.replace`/`os.rename` для этого вызова) → bundle
  восстановлен из prev, исключение наружу с ясной ошибкой.
- `test_stale_temp_dirs_cleaned` — оставить `assets.next-123` и
  `assets.prev-456` мусором; после успешного `sync()` их нет, bundle
  валиден.
- `test_successful_sync_replaces_bundle` — изменение канонического файла
  в tmp-копии `process/` → sync → bundle содержит изменение, manifest
  hash совпадает, `check()` на этой структуре rc=0.
- `test_check_detects_drift_without_modification` — искусственный drift
  (правка packaged-файла) → `check()` rc=1 и дерево не изменилось
  (сравнить sha256 до/после check).

Подготовка тестов: фикстура, копирующая минимальный набор `process/`
(schemas/templates/skills по одному файлу) и существующий сгенерированный
`assets` в tmp; `REPO`/`ASSETS` monkeypatch-сятся на неё. Реальные файлы
репозитория тестом не меняются.

### Шаг 2 — Реализация (`scripts/sync_assets.py`)

1. `_swap_in(new_dir: Path, target: Path)` — последовательность 2.3 с
   rollback и понятными исключениями.
2. `sync()`: очистка stale temp → `_generate(assets.next-…)` →
   самопроверка manifest/hashes → `_swap_in` → печать результата;
   проблемы канонических источников возвращаются как раньше (rc=1) БЕЗ
   swap.
3. Обновить docstring модуля (описать атомарность и rollback).

### Шаг 3 — Регрессия

- Полный suite + оба smoke (smoke завязан на assets через wheel? —
  по крайней мере `tests/integration/test_wheel_smoke.py` вызывает
  `sync_assets.py --check`: убедиться, что не сломано; полный wheel smoke
  запускать не обязательно, но `--check` в suite попадает).
- Реальный прогон `python scripts/sync_assets.py --check` на репозитории:
  rc=0, дерево чистое.

## 4. Границы и запреты

- Не менять формат manifest.json и состав `BUNDLE_ROOTS`.
- Не «чинить» drift автоматически в `--check` (read-only контракт
  V3-FIX-022).
- Тесты обязаны работать на Windows (rename-семантика) и POSIX —
  platform-specific поведение покрыть gейтами `sys.platform` только при
  реальной невозможности.

## 5. Acceptance

- [ ] Fault injection между генерацией и swap сохраняет предыдущий bundle
      байт-в-байт (тест зелёный).
- [ ] Искусленный drift обнаруживается `--check` без изменения дерева.
- [ ] Неуспешная генерация никогда не оставляет отсутствующий/частичный
      bundle; stale temp-каталоги вычищаются.
- [ ] Полный suite + smoke зелёные; `sync_assets.py --check` rc=0.

## 6. Evidence для RESULT.md

1. Red-вывод новых тестов.
2. Green suite + smoke; вывод `sync_assets.py --check`.
3. Демонстрация: sha256-манифест bundle до/после неудачной синхронизации
   (из теста).

## 7. Commit

Один commit: `assets: make bundle replacement atomic`.
Состав: `scripts/sync_assets.py`, `tests/unit/test_sync_assets.py`,
`RESULT.md`.
