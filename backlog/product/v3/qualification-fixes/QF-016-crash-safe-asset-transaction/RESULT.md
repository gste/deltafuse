# QF-016 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `51a2957` (QF-015)
- **Red evidence:** `tests/unit/test_sync_assets_recovery.py` — до реализации
  kill в окне между rename (`prev-moved`) оставлял target отсутствующим, а
  следующий запуск `_cleanup_stale` безусловно удалял `assets.prev-*` —
  единственную целую копию; тесты падали.

## Реализация

- **Transaction journal** (`assets.journal.json`, sibling каталога assets):
  id, target, prev, next, phase (`prepared→begin-prev→prev-moved→swapped`),
  files-hash manifest; обновляется атомарной заменой файла **до** rename,
  который он защищает.
- **`recover()` на startup — до любого cleanup**:
  - валидный target → удалить только journal-подтверждённые stale-копии;
  - target отсутствует, валидный prev → восстановить prev (byte-for-byte);
  - target отсутствует, валидный next и journal разрешает commit →
    завершить транзакцию (next становится target);
  - повреждённый journal / неоднозначное состояние → остановка БЕЗ удалений
    (exit 5).
- **`_verify_bundle` усилен**: schema manifest, точное множество файлов
  (extra packaged file = invalid), SHA-256 каждого файла, отказ
  symlink/junction внутри bundle (realtime realpath-сравнение).
- **Rollback** при неудаче второго rename сохранён (QF-009): prev
  восстанавливается, journal снимается, RuntimeError.
- Документация переименована в «crash-safe transactional replacement»
  (docstring): single-operation atomic directory replacement не заявляется.
- Тестовые хуки: `DELTAFUSE_TEST_REPO/_ASSETS`, `--recover-only`,
  crash-injection `DELTAFUSE_SYNC_CRASH_AT` (только для тестов).

## Проверки

- Hard-kill матрица в отдельных subprocess (`os._exit(137)`) на фазах
  begin-prev / prev-moved / commit / swapped + recovery новым процессом.
- Byte-for-byte hash дерева до сбоя и после recovery.
- Повреждённый journal → stop без удаления, единственная валидная копия
  цела; tampered target → валидный bundle; extra packaged file → invalid.
- После recovery `sync_assets.py --check` = 0; реальный bundle репозитория
  зелёный (44 assets).
- Ограничение: hard-kill матрица исполнена на Windows; POSIX-прогон входит в
  QF-018 (smoke/CI на POSIX).
