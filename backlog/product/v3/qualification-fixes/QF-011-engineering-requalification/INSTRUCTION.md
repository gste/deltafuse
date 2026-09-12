# QF-011 — независимая инженерная переквалификация

- **Приоритет:** P1
- **Зависимости:** QF-001–QF-010 (все коммиты пакетов уже в ветке)
- **Commit:** `release: record clean engineering qualification`
- **Исходная работа:** [qualification-fix-plan.md, QF-011](../../qualification-fix-plan.md)
- **Статус программы до начала:** `engineering-failed`

Исполнитель: читай [README.md](../README.md). Этот пакет — процедурный:
кода почти нет, основная работа — прогоны на чистом commit и фиксация
фактических результатов.

## 1. Что делается

На **чистом commit** ветки (все 10 предыдущих пакетов влиты, рабочее
дерево чистое) выполняется полный обязательный набор инженерных проверок и
сохраняются точные результаты. Это повторение независимой проверки №3, но
на исправленном коде: каждый ранее найденный блокер обязан быть закрыт
пакетами QF-001–QF-010.

## 2. Обязательный набор проверок

Все команды выполняются из корня репозитория; версия Python, pip, git и
платформа фиксируются в RESULT.md. Каждая проверка: точная команда,
rc, полный counts (никаких «~384 passed» — только точные числа), время.

1. **Полный pytest-сьют**
   `python -m pytest tests -q` (через `.venv/Scripts/python.exe` на
   Windows и соответствующий интерпретатор POSIX-окружения при наличии).
   Ожидание: 0 failed. Каждый skip — с обоснованием (файл/причина).
2. **PowerShell smoke**: `pwsh -File tests/smoke-test.ps1` → rc 0.
3. **Git Bash/POSIX smoke**: `bash tests/smoke-test.sh` → rc 0.
4. **Wheel smoke**: полный тест
   `python -m pytest tests/integration/test_wheel_smoke.py -q` → 0 failed;
   до и после — `git status --porcelain` идентичен (пустой) — это
   acceptance QF-010 на реальном прогоне.
5. **Wheel release evidence (явная команда)**:
   `python scripts/wheel_evidence.py --output-dir bench/builds` → файл
   создан, валиден; это единственное допустимое изменение tracked-файлов
   данного пакета (см. п. 4).
6. **Layout validation чистого v3-продукта**: инициализация свежего
   продукта (tmp) установленным wheel/CLI и прогоны
   `tests/validate-layout.ps1` / `tests/validate-layout.sh` против него
   (плюс штатные валидаторы продукта: `deltafuse validate-layout`,
   `deltafuse validate-config`).
7. **Поиск legacy runtime paths / compatibility adapters**: по репозиторию
   (`src/`, `scripts/`, `process/`, `docs/`):
   `git grep -nE "docs/(init|todo)/|schema_version: *2|compat" -- src scripts process docs`
   плюс ручная сверка находок: допустимы только intentional negative-
   фикстуры тестов (fail-closed на `schema_version: 2`) — каждая находка
   классифицируется в RESULT.md.
8. **Drift bundle**: `python scripts/sync_assets.py --check` → rc 0.

## 3. Критерии успеха (все обязательны)

- 0 failed по pytest; все skips обоснованы.
- Оба smoke rc 0.
- Wheel smoke прошёл, рабочее дерево до/после идентично чистое.
- Layout validation чистого v3-продукта rc 0 на обеих платформенных
  ветках (та, что доступна на машине; недоступная явно перечислена как
  «не выполнено: причина» — это не блокер, но фиксируется).
- Legacy-поиск: только intentional negative-фикстуры.
- `sync_assets --check` rc 0.

## 4. Обновление release report

`backlog/product/v3/release-report.md`:

- Раздел 3 «Независимая инженерная перепроверка» пополняется записью о
  данной переквалификации: commit SHA, дата, точные counts всех проверок,
  версии (python/pip/git/platform), статус каждой; формулировка
  «Инженерный блокер не снят» заменяется на фактическое состояние.
- Статус отчёта: `engineering-failed` → `engineering-passed / pending
  reference runs` (точную формулировку согласовать с README карточки
  DF3-009: reference runs остаются незаполненными).
- Таблица раздела 2 (runs) НЕ заполняется — это территория QF-012.

Обновляется также `backlog/product/DF3-009.md`: заметка о завершении
инженерной переквалификации со ссылкой на RESULT.md (карточка остаётся
`blocked` — снимается только QF-012).

## 5. Порядок работ

1. Убедиться: ветка содержит коммиты QF-001…QF-010; `git status --
   porcelain` пуст; зафиксировать `git rev-parse HEAD`.
2. Выполнить проверки п.2 в указанном порядке; после каждой — фиксация
   вывода в RESULT.md (команда, rc, counts).
3. Любой fail → стоп: создать finding в RESULT.md, пакет НЕ закрывается,
   status не меняется; дефект чинится отдельным fix-коммитом с собственным
   Red-тестом, затем переквалификация повторяется целиком с чистого
   commit (правило плана: «нельзя принимать по описанию агента»).
4. Обновить release-report.md / DF3-009 (п. 4).
5. Commit: обновление reports + RESULT.md + (единственное допустимое
   tracked-изменение) свежий `bench/builds/*-build-manifest.json` из п.2.5.
   Перед commit: `git status --porcelain` показывает ровно ожидаемый набор.

## 6. Acceptance

- [ ] Все обязательные проверки зелёные, точные counts сохранены.
- [ ] Каждый skip/невыполненный platform-check явно обоснован.
- [ ] Рабочее дерево до и после набора одинаково чистое (кроме явного
      wheel evidence, вошедшего в commit).
- [ ] Release report содержит точные counts и SHA, статус обновлён.
- [ ] DF3-009 остаётся `blocked` со ссылкой на QF-012.

## 7. Evidence для RESULT.md

Формат таблицей по каждой проверке: команда; rc; counts; время; версия
инструмента. Плюс: `git rev-parse HEAD`, `python --version`, `pip
--version`, `git --version`, platform (`python -c "import platform;
print(platform.platform())"`), вывод `git status --porcelain` до/после.

## 8. Commit

Один commit: `release: record clean engineering qualification`.
Состав: `backlog/product/v3/release-report.md`,
`backlog/product/DF3-009.md`, `bench/builds/*-build-manifest.json`,
`RESULT.md`.
