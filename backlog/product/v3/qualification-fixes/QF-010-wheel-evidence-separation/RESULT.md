# QF-010 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `6d5154a` (QF-009)
- **Инструменты:** Python .venv 3.12.14, pytest, pip wheel, jsonschema, Windows 10.0.26200

## Реализация

- `tests/integration/test_wheel_smoke.py`: evidence-запись в репозиторий
  удалена (env `DELTAFUSE_WHEEL_EVIDENCE_DIR` больше не используется для
  записи в `bench/builds`); блок 4 формирует evidence-объект в памяти и
  пишет его только в `tmp_path`. Новый
  `test_wheel_smoke_leaves_working_tree_clean`: `git status --porcelain`
  до/после полного wheel smoke байт-в-байт идентичны.
- `scripts/wheel_evidence.py` — явная команда durable release evidence:
  clean-tree guard (untracked тоже блокируют) → `pip wheel --no-deps` →
  wheel smoke в чистом temp-venv (CLI/init/validate-config, lock v3) →
  JSON с `commit` (полный SHA), `tree_clean: true`, `wheel`, `sha256`,
  `wheel_size_bytes`, `build_frontend` (pip wheel + версия), `build_backend`
  (setuptools), `python` (версия+impl), `platform`, `created` (UTC),
  `commands[]` (точные команды с rc). Запись атомарная; существующий файл
  не перезаписывается без `--force` (проверка ДО сборки — stem предсказуем
  из pyproject version).
- `scripts/schemas/wheel-evidence.schema.json` — валидация перед записью
  (commit 40-hex, sha256 64-hex, tree_clean const true, commands minItems 1).

## Red-фаза

Исходный факт (независимая проверка №3 п.4, наблюдался и в этой сессии до
QF-010): прогон wheel smoke/полного suite перезаписывал tracked
`bench/builds/deltafuse-3.0.0-py3-none-any-build-manifest.json`; изменение
приходилось откатывать перед каждым коммитом QF-001…QF-009.
Red-прогон новых тестов на старом smoke: падение по записи evidence в
репозиторий (`test_wheel_smoke_leaves_working_tree_clean` невозможен при
старом блоке 4) + `AttributeError`/отказ по отсутствию `wheel_evidence`.

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests
448 passed, 1 skipped, 54 warnings in 287.36s   (0 failed)
pwsh tests/smoke-test.ps1  rc=0;  bash tests/smoke-test.sh  rc=0
```

За весь прогон suite `bench/builds` больше не изменяется (git status чист
после восстановления до коммита не требовалось — впервые с начала работ
реальный прогон оставил дерево нетронутым).

## Acceptance

- [x] `git status` до/после default wheel smoke идентичен (тест зелёный).
- [x] Evidence только явной командой, в заданный output-dir, schema-valid,
      с commit/frontend/backend/python/platform/sha256/commands.
- [x] Нет молчаливой перезаписи (rc=1, sha256 файла неизменен); dirty tree
      блокирует (rc=3).
- [x] Тесты не меняют tracked files.
- [x] Полный suite + оба smoke зелёные.
