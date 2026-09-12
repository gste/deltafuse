# Qualification threat model (QF-004)

- **Статус:** актуален для runner `scripts/qualify.py` + `scripts/qualify_staging.py`
- **Scope:** qualification кампании DF3-009 (reference Worker 35B A3B), не
  продукционный runtime DeltaFuse.

## Активы

| Актив | Риск при компрометации |
|---|---|
| Judge pack (`process/bench/cases/**` — oracle, hidden_suite) | Worker читает ответы → фиктивный pass qualification |
| Host filesystem (вне sandbox) | Утечка/порча данных, обход measurement |
| Thresholds (`T1–T8`, `ABSOLUTE`) | Ослабление критериев → недействительный verdict |
| Результаты кампании (`bench/runs/**`) | Подмена reports/manifest задним числом |

## Границы и гарантии

### L1 — политика runner (реализовано, тестируется на Windows и POSIX)

1. **argv-политика** (`parse_shell_command`): allowlist head-команд
   (`deltafuse`, `pytest`, `python -m pytest`, `git status|diff|log|show`),
   точный список флагов. Запрещены: любые git-опции (закрывает `--output`,
   `--ext-diff`, `-O`, `--textconv`), pytest plugin/config/ini/import
   (`-p`, `-c`, `-o`, `--rootdir`, `--pyargs`, `--import-mode`), response
   files (`@`), `--`, UNC/сетевые/absolute пути, traversal, env-подстановки,
   shell-операторы и иные интерпретаторы. Причина отказа журналируется.
2. **Staging root** (`StagingRoot`): команды Worker исполняются в
   `work/<run_id>` — копии sandbox вне framework-репозитория. Judge pack в
   staging **физически отсутствует**: он не копируется, и переменные
   окружения, ссылающиеся на framework root, не передаются. Критерий DF3-009
   — отсутствие pack, а не полная OS-изоляция.
3. **Минимальное окружение**: PATH = контролируемый интерпретатор + git +
   системные пути; все `PYTHON*` и framework-ссылки вырезаны. Токен `python`
   исполняется контролируемым интерпретатором staging (`StagingRoot.interpreter`),
   а не случайным PATH-элементом (дефект QF-005).
4. **Сверка фактического diff** (QF-003): inventory (`git status --porcelain
   -uall`) до/после каждой команды и на границе стадии; всё, что изменилось
   вне журнала — `unjournaled_change`; всё, что появилось в staging вне
   work-каталога — `staging_escape`; сдвиг HEAD — `inventory_tampered`. Все
   три — нарушения T7 (fail).

### L2 — OS-изоляция (опция, не требуется по умолчанию)

Контейнер/VM/read-only host полностью закрывают доступ Worker-authored
Python к host FS. **Без L2 Worker-authored тестовый код в принципе может
обращаться к host filesystem** (например, по абсолютному пути, известному
из training data). Это приемлемо для qualification, потому что:
(a) judge pack отсутствует в staging физически — читать нечего;
(b) каждая команда сопровождается inventory/escape-сверкой — изменения
фиксируются и классифицируются;
(c) критерии DF3-009 требуют отсутствия pack, а не OS-изоляции.
L2 рекомендуется перед любым использованием runner за пределами
контролируемой машины разработчика.

## Платформенные гарантии

| Угроза | Windows | POSIX |
|---|---|---|
| Запись через junction/symlink | отклонена resolve-guard (`_resolve` → `Path.resolve` → escape) | отклонена аналогично (symlink) |
| Абсолютные/UNC/сетевые пути в argv | отклонены парсером (`\\`, `//`, `X:`) | отклонены (`/`, `//`) |
| `python` из случайного PATH | исключён подстановкой контролируемого интерпретатора | то же |
| Наследование env репозитория | вырезается `StagingRoot.env` | то же |
| Регистронезависимые имена/8.3-алиасы | пути сравниваются через `Path.resolve`; повреждение через алиасы покрыто inventory-diff | n/a |
| Case-insensitive коллизии имён | покрыты inventory (git) | n/a |

## Известные ограничения

- `pytest`/`python -m pytest` исполняет Worker-authored код с правами
  процесса runner (см. L2). Гарантия L1: pack недоступен, все изменения
  измеряются, интерпретатор контролируем.
- Tamper-guard обнаруживает сдвиг HEAD, но не физическую защиту `.git`;
  полная изоляция — L2/QF-004 §2.2.
- Symmetric: runner сам готовит и убирает staging; конкурентный доступ
  двух кампаний к одному staging-каталогу не поддерживается (base per campaign).
