# DeltaFuse 3.0 — план исправления qualification

- **Статус:** `ready`
- **Основание:** независимая повторная проверка 2026-09-12
- **Заменяет для исправлений:** [completion-plan.md](completion-plan.md)
- **Цель:** сделать доказательным qualification слабого Worker класса 35B A3B
  при полном окне от 32k, не ослабляя T1–T8 и не используя baseline v2

План разбит на небольшие последовательные пакеты. Каждый пакет завершается
отдельным reviewable commit, собственным Red/Green-тестом и проверкой регрессий.
Следующий пакет нельзя принимать по описанию агента: нужны сохранённые результаты
команд и проверяемое состояние дерева.

## Что действительно подтверждено

- `apply_thresholds` переведён на фактические агрегаты `score_product`.
- Удалён `shell=True` и добавлен структурированный разбор `argv`.
- Удалён повторный Intake `advance`; контракт Core-команд зафиксирован тестом.
- Добавлены YAML manifest/report и расширен wheel smoke.

Эти изменения не закрывают qualification целиком. Независимый прогон дал
`1 failed, 382 passed, 1 skipped`; оба smoke-теста прошли. Девять реальных
прогонов не выполнялись.

## QF-001 — fail-closed write envelope

- **Приоритет:** P0
- **Дефект:** пустой или неразобранный `envelope.write` разрешает любую запись.
  Условие в `SandboxIO.write_file` проверяет glob только при непустом списке,
  а `_core_envelope` возвращает пустой список при ошибке Core.
- **Риск:** Worker может записать `src/evil.py`, когда Core не выдал разрешений.
- **Исправление:** различать «envelope успешно получен и пуст» и «envelope
  недоступен/невалиден»; оба состояния запрещают любые product writes, кроме
  явно перечисленных внутренних файлов qualification. Ошибка Core блокирует
  stage, а не расширяет права.
- **Red:** integration test с пустым envelope пытается записать product-файл и
  обязан получить отказ; отдельные тесты на malformed JSON, timeout и non-zero
  Core exit.
- **Acceptance:** разрешаются только пути, совпавшие с текущим Core envelope;
  любая потеря измерения или ошибка Core даёт fail и ненулевой exit code.

## QF-002 — корректное измерение T5 по каждому вызову

- **Приоритет:** P0
- **Дефект:** runner сохраняет `call_unique_files` до выполнения tool action и
  затем сбрасывает счётчик. Поэтому реальное чтение последним действием вызова
  даёт `0`, а T5 не измеряется.
- **Исправление:** создать типизированный журнал tool events; выполнять action,
  затем закрывать measurement конкретного вызова. Учитывать read, write и пути,
  фактически затронутые разрешённой shell-командой.
- **Red:** Worker читает один файл последним действием; отчёт обязан показать
  `unique_files: 1`. Добавить кейсы с несколькими действиями и повторным чтением.
- **Acceptance:** T5 содержит максимум уникальных файлов одного вызова, включая
  последнее действие; повтор одного пути не увеличивает значение.

## QF-003 — T7 по фактическим изменениям текущего stage

- **Приоритет:** P0
- **Зависит от:** QF-001, QF-002
- **Дефект:** leash получает общий накопительный набор reads+writes за весь run,
  а shell-created files не учитываются. Файлы прошлых стадий и чтения ошибочно
  проверяются по envelope текущей стадии.
- **Исправление:** разнести read/write telemetry; перед и после каждого action и
  stage получать фактический changed-path inventory через изолированный checkout
  и Core. Проверять только записи текущей стадии по envelope, действовавшему в
  момент записи; запускать Core leash после каждого перехода.
- **Red:** shell-команда создаёт файл вне envelope; файл обнаруживается и T7
  падает. Чтение разрешённого файла и изменение файла прошлой стадии не дают
  ложной классификации текущей стадии.
- **Acceptance:** ни один изменённый путь не остаётся вне журналирования; T7
  определяется ответом Core и фактическим diff, а не локальным счётчиком.

## QF-004 — реальная граница исполнения Worker

- **Приоритет:** P0
- **Дефект:** allowlist executable недостаточен. Например,
  `git diff --output=leak.txt` принимается и пишет файл; разрешённый `pytest`
  исполняет Worker-authored Python с доступом к host filesystem. Judge pack
  изолирован только соглашением, а не системной границей.
- **Исправление:** ввести точную политику subcommand/options и минимальное
  окружение. Qualification Worker запускать в отдельном процессе/контейнере или
  временной машине, где judge pack физически отсутствует, а sandbox является
  единственным writable root. После каждой команды сверять фактический diff.
- **Red:** adversarial matrix для output/config/plugin/import options, response
  files, symlink/junction, traversal, absolute/UNC paths и запуска тестового кода,
  читающего judge pack или host-файл.
- **Acceptance:** ни одна разрешённая команда не читает judge pack и не пишет
  вне sandbox; threat model и platform guarantees явно описаны и проверены на
  Windows и POSIX.

## QF-005 — контролируемый Python и environment

- **Приоритет:** P0
- **Дефект:** разрешённая команда `python -m pytest` берёт `python` из PATH.
  Независимый suite упал в
  `tests/unit/test_qualify.py::test_allowed_shell_commands_still_run`, потому
  что выбранный интерпретатор не содержал pytest.
- **Исправление:** нормализовать разрешённый Python к контролируемому
  `sys.executable`/runner interpreter; передавать очищенные PATH, cwd и env без
  Worker-controlled injection.
- **Red:** PATH начинается с другого Python без pytest; разрешённый тест всё
  равно использует qualification interpreter. Запрещённые env overrides
  отклоняются.
- **Acceptance:** один и тот же argv-контракт проходит на Windows и POSIX и не
  зависит от случайного Python в PATH.

## QF-006 — буквальные T4, T6 и T8

- **Приоритет:** P0
- **Зависит от:** QF-002–QF-004
- **Дефекты:**
  - T4 оценивает токены как `len(chars) // 4`, смешивает product content с
    framework-controlled input и не использует tokenizer host.
  - T6 не получает все выдуманные shell/read/write paths; часть нарушений
    ошибочно попадает в T7.
  - T8 проходит при пустом `defense_checks`, то есть отсутствие доказательства
    трактуется как успех.
- **Исправление:** маркировать provenance каждого сообщения; считать полный
  input по host usage/tokenizer и отдельно skills/Core/framework. Классифицировать
  пути из типизированного tool journal. Задать обязательный набор T8 evidence
  checks для каждого case; отсутствие любого результата означает fail.
- **Red:** mutation test отдельно для границы и отсутствующего измерения T4, T6,
  T8; пустой `defense_checks` обязан провалить verdict.
- **Acceptance:** все три threshold имеют измеряемый источник в report; `0` не
  подставляется вместо `unknown`, а `unknown` не может дать pass.

## QF-007 — проверяемый host attestation

- **Приоритет:** P1
- **Дефект:** `cloud_fallback: false` сейчас записывается как константа, а не
  измеряется; tokenizer identity/config не фиксируются полностью.
- **Исправление:** проверить точный model ID и context limit от host, выполнить
  diagnostic completion с валидным usage, сохранить tokenizer identity/hash и
  model parameters/state. Для запрета fallback использовать подтверждаемую
  host-конфигурацию либо честно обозначенный, документированный инвариант.
- **Red:** mismatch model/context/tokenizer, отсутствие usage и недоказанный
  fallback каждый отдельно блокируют кампанию.
- **Acceptance:** manifest различает измеренные, заявленные и выведенные поля;
  непроверяемое обязательное свойство не публикуется как факт.

## QF-008 — schema, медианы и сохранение отказов

- **Приоритет:** P1
- **Дефекты:** disk report не соответствует формату `thresholds.md`; нет
  `totals`, `evidence_authentic` и полных aggregate verdicts. `medians()` не
  считает process. `runs_ok` может протекать между cases. Ошибка HTTP/score/I/O
  способна завершить run без failure report.
- **Исправление:** формализовать JSON/YAML schema для manifest и report; считать
  correctness и process для каждого run и медианы каждого case; сбрасывать
  состояние по case. Любую ожидаемую ошибку классифицировать и атомарно сохранять
  перед выходом.
- **Red:** кампания 3x3 с одним failed run, одним отсутствующим measurement и
  одной ошибкой записи/host; все начатые runs представлены в manifest/report,
  общий exit ненулевой.
- **Acceptance:** schema validation проходит на всех сохранённых файлах;
  незавершённый набор, failed run или failed median не может дать pass.

## QF-009 — атомарная синхронизация assets

- **Приоритет:** P1
- **Дефект:** `sync_assets.py` сначала удаляет целевой bundle, затем генерирует
  новый; это не атомарная замена и противоречит заявленному результату.
- **Исправление:** генерировать во временном sibling-каталоге, проверить manifest
  и hashes, затем выполнить атомарный swap с rollback. `--check` сверяет
  canonical source, manifest и packaged files.
- **Red:** fault injection между генерацией и swap сохраняет предыдущий bundle
  байт-в-байт; искусственный drift обнаруживается без изменения дерева.
- **Acceptance:** неуспешная генерация никогда не оставляет отсутствующий или
  частичный bundle.

## QF-010 — чистый и воспроизводимый wheel evidence

- **Приоритет:** P1
- **Дефект:** wheel smoke по умолчанию перезаписывает отслеживаемый
  `bench/builds/*-build-manifest.json`; Python version и wheel hash меняются,
  поэтому обычный тест загрязняет рабочее дерево.
- **Исправление:** тест пишет только в `tmp_path`. Durable release evidence
  создаётся отдельной явной командой в заданном output directory и содержит
  commit, build frontend/backend и воспроизводимые provenance fields.
- **Red:** сравнить `git status` до/после default wheel smoke; дерево остаётся
  неизменным. Проверить явный output и отсутствие auto-fix при drift.
- **Acceptance:** тесты не меняют tracked files; release evidence создаётся
  только по явному запросу и валидируется схемой.

## QF-011 — независимая инженерная переквалификация

- **Приоритет:** P1
- **Зависит от:** QF-001–QF-010
- **Работа:** на чистом commit выполнить полный pytest, PowerShell smoke, Git
  Bash/POSIX smoke, wheel smoke, layout validation чистого v3-продукта и поиск
  legacy runtime paths/compatibility adapters. Сохранить точные команды, версии,
  counts, SHA и output artifacts.
- **Acceptance:** все обязательные проверки зелёные, skips обоснованы, рабочее
  дерево до и после одинаково чистое. Release report содержит точные counts, а
  не округление `~384 passed`.

## QF-012 — реальная reference qualification и закрытие

- **Приоритет:** P1
- **Зависит от:** QF-011 и доступного LM Studio host
- **Работа:** на `ornith-1.5-35b-a3b`, context 32768, без cloud/mock fallback
  выполнить по три независимых чистых прогона M01, M02 и M03. Не выбирать лучший
  run и не менять thresholds по результатам.
- **Acceptance:** сохранены все девять reports и campaign manifest; каждый run,
  медианы correctness/process и T1–T8 проходят. Только после этого отдельным
  commit перевести DF3-009, release report и программу в `done`.

## Порядок коммитов

1. `qualify: fail closed on missing write envelope` — QF-001.
2. `qualify: measure files per worker call` — QF-002.
3. `qualify: enforce leash against stage changes` — QF-003.
4. `qualify: isolate worker command execution` — QF-004.
5. `qualify: pin interpreter and environment` — QF-005.
6. `qualify: make T4 T6 T8 evidence literal` — QF-006.
7. `qualify: attest reference host` — QF-007.
8. `qualify: validate reports and preserve failures` — QF-008.
9. `assets: make bundle replacement atomic` — QF-009.
10. `wheel: separate smoke from release evidence` — QF-010.
11. `release: record clean engineering qualification` — QF-011.
12. `release: record reference qualification` — QF-012.

## Запрет преждевременного закрытия

Предыдущая формулировка «шаги 1–8 выполнены» не является acceptance evidence.
До QF-011 статус программы остаётся `engineering-failed`; до QF-012 DF3-009
остаётся `blocked`. Отсутствие LM Studio не мешает исправить QF-001–QF-011 и не
разрешает синтетически заполнять результаты reference runs.
