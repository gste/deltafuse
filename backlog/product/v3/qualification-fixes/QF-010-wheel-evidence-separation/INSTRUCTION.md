# QF-010 — чистый и воспроизводимый wheel evidence

- **Приоритет:** P1
- **Зависимости:** нет (независим от qualify-пакетов; можно выполнять
  параллельно с P0-очередью)
- **Commit:** `wheel: separate smoke from release evidence`
- **Исходный дефект:** [qualification-fix-plan.md, QF-010](../../qualification-fix-plan.md)
- **Код на момент написания:** commit `bb02820`

Исполнитель: читай [README.md](../README.md) до начала работы.

## 1. Дефект

`tests/integration/test_wheel_smoke.py` (блок 4, bb02820) после каждой
проверки записывает evidence в каталог репозитория по умолчанию:

```python
evidence_dir = Path(
    os.environ.get("DELTAFUSE_WHEEL_EVIDENCE_DIR", REPO_ROOT / "bench" / "builds")
)
...
evidence = evidence_dir / f"{wheel.stem}-build-manifest.json"
evidence.write_text(...)
```

`bench/builds/deltafuse-3.0.0-py3-none-any-build-manifest.json` —
отслеживаемый файл. Python-версия и wheel hash меняются от машины к машине,
поэтому обычный прогон теста **пачкает рабочее дерево** (подтверждено
независимой проверкой №3, пункт 4: manifest перезаписан, изменение
пришлось откатывать). Тест, который по определению должен подтверждать
чистоту операций, сам нарушает её.

Одновременно отсутствует штатный способ создать durable release evidence:
нужна отдельная явная команда с воспроизводимыми provenance-полями.

## 2. Нормативное поведение

1. **Тест пишет только в `tmp_path`.** Default wheel smoke не трогает
   ничего вне tmp: `git status --porcelain` до и после идентичны. Переменная
   `DELTAFUSE_WHEEL_EVIDENCE_DIR` из теста удаляется (вместе с записью в
   репозиторий); evidence-блок теста проверяет форму evidence-объекта,
   сериализуя его в `tmp_path`.
2. **Durable release evidence — отдельная явная команда.** Новый скрипт
   `scripts/wheel_evidence.py`:

   ```
   python scripts/wheel_evidence.py --output-dir bench/builds [--repo .]
   ```

   Действия: clean-tree guard (как в qualify provenance) → build wheel
   (`pip wheel --no-deps`) → wheel smoke в temp venv (CLI/init/
   validate-config, как в тесте) → записать в `<output-dir>/<wheel-stem>-
   build-manifest.json`:
   - `commit` (полный SHA), `tree_clean: true`;
   - `wheel` имя + `sha256`; `wheel_size_bytes`;
   - `build_frontend` (`pip wheel`, версия pip), `build_backend`
   (setuptools версия из venv), `python` (версия + impl + platform),
   - `created` UTC ISO-8601;
   - `commands[]` — точные выполненные команды с rc.
   Запись атомарная; существующий файл не перезаписывается молча без
   `--force` (иначе два прогона на одной версии будут затирать друг друга
   бесшумно).
3. **Схема evidence.** JSON Schema `scripts/schemas/wheel-evidence.schema.json`
   (валидация перед записью; обязателен commit/sha256/python/platform).
4. Тест wheel smoke сохраняет семантику «no auto-fix on drift» (уже так) и
   семантику «pip недоступен — явный fail, не skip» (уже так).

## 3. План работ

### Шаг 1 — Red-тесты

`tests/integration/test_wheel_smoke.py`:

- `test_wheel_smoke_leaves_working_tree_clean` — прогон smoke в tmp;
  `git status --porcelain` репозитория до и после байт-в-байт совпадает
  (сегодня: меняется tracked build-manifest).

Новый `tests/integration/test_wheel_evidence.py` (запуск реальной сборки —
тяжёлый; пометить маркером, который включён в стандартный suite, но с
переиспользованием session-fixture сборки, как в QF-004):

- `test_evidence_written_only_on_explicit_call` — вызов скрипта с
  `--output-dir tmp_path`: файл создан, валиден по схеме, содержит commit/
  sha256/commands.
- `test_evidence_refuses_dirty_tree` — dirty guard: подмена `tree_dirty` →
  rc≠0, файл не создан.
- `test_evidence_no_silent_overwrite` — повторный вызов без `--force` при
  существующем файле → rc≠0, файл не изменён (sha256 до/после).

### Шаг 2 — Реализация

1. Убрать evidence-запись из `test_wheel_smoke.py` (п.2.1): блок 4
   заменяется на формирование объекта evidence в памяти + дамп в tmp_path
   + валидация по схеме (это и есть smoke покрытия evidence-формы).
2. `scripts/wheel_evidence.py` (п.2.2) + схема (п.2.3).
3. Обновить docstring теста и, при необходимости, раздел testing-strategy
   docs (`docs/testing-strategy.md` / `.ru.md` — упоминается ли wheel
   evidence: согласовать формулировки «evidence только по явной команде»).

### Шаг 3 — Регрессия

- Полный suite + оба smoke.
- Явная демонстрация: `python scripts/wheel_evidence.py --output-dir
  <tmp>` → файл; `git status --porcelain` репозитория чист.

## 4. Границы и запреты

- Не удалять существующий tracked `bench/builds/deltafuse-3.0.0-…-build-
  manifest.json` — это durable release evidence; обновляется только
  явной командой в момент release (QF-011).
- Не ослаблять существующие проверки smoke (clean venv, no checkout on
  sys.path, lock v3, validate-config).
- Скрипт не запускается из тестов с записью в репозиторий.

## 5. Acceptance

- [ ] `git status` до/после default wheel smoke идентичен (тест зелёный).
- [ ] Release evidence создаётся только явной командой, в заданный
      output-dir, валидируется схемой, содержит commit/frontend/backend/
      python/platform/sha256/commands.
- [ ] Нет молчаливой перезаписи существующего evidence; dirty tree
      блокирует.
- [ ] Тесты не меняют tracked files (инвариант suites).
- [ ] Полный suite + smoke зелёные.

## 6. Evidence для RESULT.md

1. Red-вывод (до/после `git status --porcelain` вокруг старого поведения —
   можно воспроизвести вручную на отдельной машине-копии, либо привести
   вывод независимой проверки №3 п.4 как исходный факт + новый зелёный
   тест).
2. Green suite + smoke; листинг файла evidence из явного вызова в tmp.

## 7. Commit

Один commit: `wheel: separate smoke from release evidence`.
Состав: `tests/integration/test_wheel_smoke.py`,
`tests/integration/test_wheel_evidence.py`, `scripts/wheel_evidence.py`,
`scripts/schemas/wheel-evidence.schema.json`, `RESULT.md`, ± docs
(testing-strategy).
