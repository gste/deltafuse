# QF-023 — результат исполнения

- **Статус:** выполнено
- **Базовый commit (parent):** `8739d4efe3807ec52e563cc2c0332ce686bbec8f` (QF-022)
- **Итоговый commit:** тот, в котором лежит этот файл (child of base)
- **Инструменты:** Python 3.12.14 (.venv, CPython), pytest 9.1.1, Windows
  10.0.26200 (win32)
- **Red evidence:** `tests/unit/test_sync_assets_hash_coverage.py` на базовом
  commit — 8/8 тестов падали: `__init__.py` обязателен в exact file set, но
  отсутствовал в manifest hashes (подмена маркера не обнаруживалась ни
  `_verify_bundle`, ни `--check`), recovery принимал копию с подменённым
  маркером, а `--check` не проверял типы entries в закоммиченном bundle.

## Реализация

- **`_generate`**: `__init__.py` включён в manifest `files` со своим SHA-256;
  содержимое маркера пишется `write_bytes` (LF) — `write_text` применял
  платформенный перевод строк (CRLF на Windows), делая хешированный маркер
  платформенно-зависимым и bundle неверифицируемым между хостами (тот же
  класс дефекта, что чинил `141c2ae` для skills).
- **`_verify_bundle`**: exact file set = manifest `files` ∪ {manifest.json};
  маркер больше не special-case — подмена/удаление/лишний файл обнаруживаются;
  `_is_reparse_point` усилен: lstat reparse-атрибуты
  (`FILE_ATTRIBUTE_REPARSE_POINT`) + `islink`, строковое сравнение realpath
  осталось как fallback; исключения для `__pycache__`/`.pytest_cache`
  выровнены с генератором (runtime-импорты в source-дереве не часть
  контракта bundle — найдено строгой проверкой на wheel smoke).
- **`check()`**: добавлен шаг полного `_verify_bundle(ASSETS)` (read-only) —
  `--check` теперь отклоняет symlink/junction/reparse в закоммиченном bundle,
  а не только hash/manifest drift.
- **Recovery**: `_valid()` использует усиленный `_verify_bundle` — копия с
  подменённым `__init__.py` невалидна; recovery выбирает только полностью
  верифицированную копию; неоднозначное состояние (все копии невалидны)
  останавливается БЕЗ удалений.
- **Tracked bundle** перегенерирован явной командой `python scripts/sync_assets.py`
  (45 assets, манифест содержит hash маркера; `--check`: up to date).

## Проверки

| # | Команда | Результат |
|---|---|---|
| 1 | Red: `pytest tests/unit/test_sync_assets_hash_coverage.py -q` на `8739d4e` | 8 failed (подмена/удаление маркера и reparse-матрица не обнаруживались) |
| 2 | тот же файл + recovery/sync-сьюты после реализации | 0 failed |
| 3 | Полный suite: `pytest tests -q --junitxml=…` | tests=637, failures=0, errors=0, **skipped=7**, exit 0 (630 passed) |

Mutation-матрица: подмена `__init__.py` (`--check` rc≠0 + `_verify_bundle`
RuntimeError); удаление маркера; лишний executable; junction на каталог вне
bundle; «сломанная» ссылка (junction с удалённым target); nested link;
reparse в закоммиченном bundle ловится `--check`; recovery: crash
prev-moved + tampered prev → коммитится верифицированный next; tampered
prev+next → остановка БЕЗ удалений (exit 5). Hard-kill матрица QF-016
(`test_sync_assets_recovery.py`) осталась зелёной на Windows.

Ограничения: POSIX-прогон lstat/islink ветки выполнен через единый код
(`os.path.islink` + lstat); нативная Linux-машина недоступна — POSIX-ветка
hard-kill матрицы не запускалась (зафиксировано; не блокер для пакета,
требуется в QF-025 evidence по возможности). Изменение permissions не часть
контракта bundle на win32 (noted; POSIX-режимы не хешируются — контракт
файлов, не метаданных).
