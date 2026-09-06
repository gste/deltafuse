# Результат эксперимента A09-01

- **ID карточки:** A09-01 (дети A09-01a/b/c)
- **Ревизия старта:** `e57dc9d`
- **Статус исполнения:** **in-progress**
- **Критерии:** `SPEC-001`, `SPEC-002`, `CODE-001`, `TEST-001`, `PROC-004`, `PROC-007`
- **Промежуточный вердикт A09-01a / S02 r1 Intake (протокол как в protocol.md):** **fail** по F-007, не по FSM продукта

## Сплит

До исполнения созданы [A09-01a](../../packets/A09-01a.md) (S02), [A09-01b](../../packets/A09-01b.md) (S03), [A09-01c](../../packets/A09-01c.md) (S04).

## S02 r1 Intake, конфиг протокола (`max_tokens: 2048`, thinking включён)

Две полные попытки: `content` пустой, `finish_reason: length`, 465 с и 714 с. Change-пакет не создан. Третья попытка остановлена как повторение той же ошибки. Finding: [F-007](../../../findings/F-007.md).

Логи: [runs/S02/r1/intake/](runs/S02/r1/intake/).

## Калибровка schema-8k (S02 r1-schema-8k)

Модель записала валидный пакет `CHG-107-ratelimit-cooldown-penalty` (`schema_version`, `title`, `framework.content_hash` из lock, пустые `deltas/slices/decisions/tasks`). Независимый `check_gate(..., intake)` и `validate_change_package` на этом каталоге: **0 ошибок**.

Harness сначала засчитал **fail**: `find_change_dir` брал лексикографически первый каталог `CHG-001-*` (невалидный артефакт предыдущей попытки). Это ошибка экспериментального раннера, не модели. Исправлено: выбирать пакет из `written` / по mtime.

Длительность 1177 с, reasoning ~15k символов, VRAM ~7600 MiB. Intake S02 r1 с калиброванным конфигом (`max_tokens: 8192`, схема в контексте) **проходит гейт**.

## Analyze S02 r1-schema-8k

Один вызов остановлен после ~1812 с (лимит пакета 30 мин). `response.json` не записан — поток llama-server всё ещё слал reasoning. Промпт: skill Analyze + 4 схемы + spec + CHG-107. Калибровка дальше: резать Analyze на подшаги (routing → slices → coverage) или глушить thinking на стороне llama-server.

Логи: [runs/S02/r1-schema-8k/analyze/](runs/S02/r1-schema-8k/analyze/).

## Заморозка калибровки (черновик, не holdout)

| Параметр | Протокол A08 | Рабочее на Intake S02 |
|---|---|---|
| max_tokens | 2048 | **8192** (иначе reasoning съедает лимит, F-007) |
| timeout на вызов | 180 с | **900+ с** (факт 465–1177 с) |
| enable_thinking: false | — | **не выключает** reasoning у ornith в этом LM Studio |
| /no_think в system | — | content появляется |
| схемы в контексте Intake | skill требует | **нужны**, иначе additionalProperties fail |
| timeout пакета | 30 мин | Analyze в одном JSON-вызове **не укладывается** |

## Handoff

- **Готово:** сплит A09-01a/b/c; harness; F-007; Intake S02 r1 pass на CHG-107; продукт `experiments/A09-01/work/S02-r1/`.
- **Продолжить A09-01a:** frozen [local-runtime](../local-runtime/README.md) `:1240`; Intake-smoke; Analyze только `routing.yaml` (`A09_ANALYZE_FOCUS=routing`); затем slices/coverage; три повтора S02; A09-01b/c.
- **Не стартовать holdout** и не менять skills фреймворка без A12.
- **Runtime:** оптимизация L/W закрыта. Новых bear-тестов не открывать, пока A09 не даст другую боль.
