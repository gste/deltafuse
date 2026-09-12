# DeltaFuse 3.0 — completion plan

- **Статус:** `ready`
- **Основание:** повторная проверка исполнения плана 2026-09-12
- **Цель:** сделать qualification доказательным для слабого Worker класса
  35B A3B в полном окне от 32k, затем завершить DF3-009 реальными прогонами
- **Baseline v2:** не используется

Каждый шаг должен завершаться отдельным reviewable commit. Следующий шаг нельзя
начинать, пока acceptance предыдущего не подтверждён тестом или сохранённым
run artifact.

## Шаг 1 — восстановить исполнимость runner

Исправить `apply_thresholds`: использовать реальную структуру результата
`score_product` (`checks` — список, агрегаты находятся в `checks_failed` /
`checks_total`). Добавить integration test `score_product -> apply_thresholds`,
а не только искусственный словарь другой формы.

**Acceptance:** законченный synthetic run доходит до записи per-run report без
`AttributeError`; ошибка любого check отражается в T1.

## Шаг 2 — закрыть выход из sandbox

Убрать `shell=True` и строковый prefix allowlist. Принимать структурированный
`argv`, разрешать только точные команды/подкоманды и запрещать shell operators,
absolute paths, traversal, environment injection и запуск произвольных
интерпретаторов. Judge pack и host filesystem не должны быть доступны Worker.

**Acceptance:** adversarial tests для `&`, `&&`, `|`, redirection, PowerShell,
`cmd`, command substitution и absolute paths не создают и не читают файл вне
sandbox; разрешённые DeltaFuse/pytest/git read-only команды продолжают работать.

## Шаг 3 — исправить Worker-контракты

Удалить повторный `deltafuse advance --gate intake`. Проверить каждый skill и
generated asset: один успешный `check-gate` вызывает ровно один `advance`, а
изменение task/slice/Change state выполняется только `deltafuse state`.

**Acceptance:** новый contract test проверяет точное число и порядок Core-команд
для всех семи skills; first-write/through-mode проходит Intake и переходит к
Analyze без ложной остановки.

## Шаг 4 — реализовать T1–T8 буквально

- T1: ноль проваленных oracle checks по фактическим агрегатам scorecard.
- T2: ровно семь завершённых этапов, без skipped/aborted.
- T3: не более двух retries суммарно и не более одного на каждый stage.
- T4: fail-closed при отсутствии tokenizer/usage; измерять весь input и отдельно
  весь framework-controlled input, включая skills и ответы Core.
- T5: считать уникальные файлы для каждого вызова, включая последнюю tool action.
- T6: учитывать выдуманные read/write/shell paths.
- T7: ограничивать `write_file` текущим `envelope.write` и запускать leash после
  каждого этапа; результат брать из Core, а не из локального счётчика.
- T8: проверять authentic evidence для каждого case, даже если case не объявил
  дополнительные adversarial checks.

**Acceptance:** отдельный mutation test на каждую границу T1–T8 меняет verdict
на `fail`; отсутствие измерения также даёт `fail`, а не ноль или `unknown` pass.

## Шаг 5 — привести host probe к контракту

Проверять точный model ID, фактический context limit 32768, tokenizer/model
parameters и отсутствие cloud/mock fallback. Не записывать константу как будто
это измеренный параметр. Диагностический completion обязан вернуть валидный
usage/tokenization result.

**Acceptance:** несовпадение model/context/tokenizer/fallback блокирует кампанию;
проверенные параметры входят в immutable manifest.

## Шаг 6 — сделать provenance и verdict fail-closed

Перед кампанией требовать чистое рабочее дерево и фиксировать полный commit SHA,
framework content hash, thresholds revision и host/model manifest. Писать
`manifest.yaml` и `report.yaml` по формату `thresholds.md`, атомарно обновляя
manifest после каждого прогона. Сохранять partial/failure results.

Применять thresholds к каждому прогону и медианам. Любой failed run, failed
median, незавершённый набор или ошибка записи должны давать ненулевой exit code.

**Acceptance:** schemas/contract tests проверяют полный disk format; кампания из
трёх синтетических runs с одним failure завершается non-zero и сохраняет все
три результата и общий verdict.

## Шаг 7 — завершить asset и wheel tooling

`sync_assets.py` должен генерировать bundle во временный каталог и заменять
целевой только после полной успешной проверки. `--check` должен сверять как
canonical source с manifest, так и фактические packaged files с manifest.

Wheel smoke не должен исправлять source tree при drift. Он обязан построить
wheel, установить его в clean venv, выполнить CLI/init/`validate-config`,
проверить независимость от checkout и сохранить durable build manifest. В
release suite отсутствие `pip`/build tool является явным blocked/fail, а не
молчаливым skip.

**Acceptance:** искусственный drift обнаруживается без изменения дерева;
прерванная генерация сохраняет предыдущий bundle; wheel evidence остаётся после
теста в заданной output directory.

## Шаг 8 — повторная инженерная квалификация

На чистом commit выполнить:

1. полный pytest;
2. `tests/smoke-test.ps1`;
3. `tests/smoke-test.sh` через Git Bash/POSIX;
4. wheel smoke;
5. layout validation для clean v3 product;
6. поиск legacy runtime paths и compatibility adapters.

Обновить release report фактическими числами, platform и commit SHA.

**Acceptance:** обязательные проверки зелёные; исключения и skips явно
обоснованы, а рабочее дерево после проверок чистое.

## Шаг 9 — реальные 35B/32k прогоны

На LM Studio с `ornith-1.5-35b-a3b` и context 32768 выполнить по три независимых
чистых прогона M01, M02 и M03. Cloud/mock fallback запрещён. Не выбирать лучший
run и не ослаблять thresholds по результатам.

**Acceptance:** все девять report-файлов и campaign manifest сохранены; каждый
run и медианы проходят T1–T8.

## Шаг 10 — закрытие программы

Обновить `release-report.md`, DF3-009, `product/index.md` и `deltafuse-3.md` одним
commit. Статус `done` допустим только после полного pass шага 9.

