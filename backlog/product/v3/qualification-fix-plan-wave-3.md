# DeltaFuse 3.0 — qualification fix plan, wave 3

- **Статус:** `ready`
- **Основание:** независимая приёмка Wave 2 на commit `01037cd`, 2026-09-13
- **Предыдущая волна:**
  [qualification-fix-plan-wave-2.md](qualification-fix-plan-wave-2.md)
- **Цель:** сделать isolated execution реально исполнимым и доказательным,
  обеспечить независимый пересчёт T1–T8 и восстановить достоверный release
  evidence до возобновления QF-012
- **Reference Worker:** локальная LLM класса 35B A3B, context от 32k
- **Baseline v2:** не используется

Wave 2 сохраняется как история. Этот файл — отдельная очередь QF-019–QF-025.
Каждый пакет ограничен одним главным инвариантом, чтобы его могла качественно
реализовать слабая LLM в ограниченном контексте. До полного QF-025 release
status остаётся `engineering-failed / correction wave 3`.

## Подтверждённое основание

На commit `01037cd` независимо подтверждено:

- `534 passed, 6 skipped`; пять skips — live container boundary, один — PBT;
- PowerShell и Git Bash smoke прошли; asset drift отсутствует;
- isolated executor без runtime/image корректно возвращает `PENDING`, exit 2;
- QF-014 exact lifecycle работает;
- QF-015 не разрешает estimated tokenizer поддерживать release pass;
- QF-016 восстанавливается после hard crash на Windows;
- при этом текущий container entrypoint не исполним с заявленным wheel-only
  image, boundary probe проверяет не ту поверхность, semantic validator
  пропускает очевидно нарушающий T1–T8 `pass`, а durable wheel evidence устарел.

## Общие правила

1. Один пакет — один reviewable commit с кодом, Red→Green-тестами и отдельным
   `RESULT.md`.
2. Red evidence должен падать на родительском commit именно по исправляемому
   инварианту. Monkeypatch не заменяет live boundary evidence.
3. `RESULT.md` фиксирует полный parent SHA, итоговый SHA, точные команды, exit
   codes, counts, platform и пути к сохранённым artifacts.
4. QF-019–QF-021 — последовательные P0-пакеты. QF-022 и QF-023 можно выполнять
   независимо, но QF-024 начинается только после QF-019–QF-023.
5. Нельзя менять T1–T8 или вводить новый численный допуск без maintainer
   Decision, записанного до реализации.
6. Ни skip, ни `PENDING`, ни local-dev результат не считаются release evidence.
7. Каждый пакет заканчивается чистым деревом; тесты не переписывают tracked
   evidence.

## QF-019 — исполнимый judge-free command executor

- **Приоритет:** P0
- **Исходный дефект:** Worker-контейнер получает только `/opt/qualify.py`, но
  файл импортирует `qualify_executor` и `qualify_semantic`, отсутствующие в
  wheel. Заявленная конфигурация завершается `ModuleNotFoundError` до Worker.
- **Инвариант:** Worker-authored shell-команды выполняются в одной
  воспроизводимой изолированной среде, которой не нужны judge-side scripts,
  framework checkout или bench pack.

### Архитектура

1. Оставить model calls, tool orchestration, scoring и report generation на
   judge host.
2. Перенести внутрь изоляции только выполнение разрешённых Worker shell argv.
   `read_file`/`write_file` остаются judge-side и проходят существующие
   envelope/path guards.
3. На каждый run запускать persistent command container:
   - image содержит установленный wheel DeltaFuse, pytest и git;
   - монтируется только sandbox этого run;
   - cwd внутри контейнера — sandbox;
   - host передаёт уже разобранный argv, получает stdout/stderr/exit code;
   - контейнер не получает `qualify.py`, helper modules, pack или checkout.
4. Ввести интерфейс `CommandExecutor.run(argv, cwd, timeout) -> CommandResult`.
   `SandboxIO.shell` не вызывает `subprocess.run` напрямую в release mode.
5. Добавить канонический `Containerfile` и `scripts/build_qual_image.py`:
   - сначала строится wheel из чистого commit;
   - image строится только из wheel и pinned tool dependencies;
   - сохраняются image digest, wheel hash и build manifest;
   - tag без digest не принимается для release.
6. `local-dev` использует отдельный `LocalCommandExecutor` и по-прежнему имеет
   verdict cap `non-release`.

### Red tests

- Моделирование image `wheel + pytest + git` запускает разрешённые
  `deltafuse`, `pytest` и `git status` без imports из `scripts/**`.
- Удаление checkout после сборки image не ломает command execution.
- Попытка выполнить release shell через local subprocess блокируется.
- Container exit, timeout и malformed output классифицируются и сохраняются.
- Image с другим wheel hash/digest не проходит attestation.

### Acceptance

- Live smoke выполняет разрешённую команду в контейнере и сохраняет результат.
- В mounts отсутствуют framework checkout, judge pack и runner scripts.
- Образ воспроизводимо собирается одной документированной командой.
- Manifest содержит измеренные image digest и wheel SHA текущего commit.

## QF-020 — boundary probe той же среды и строгая network policy

- **Приоритет:** P0
- **Зависит от:** QF-019
- **Исходные дефекты:** sentinel создаётся внутри mounted sandbox, но probe
  проверяет несуществующий host path; probe запускается с `--network none`, а
  Worker — в другом контейнере с bridge network. Image/mount/network attestation
  преимущественно declared, а не измерена.
- **Инвариант:** probe и Worker-команды исполняются в одном persistent container
  с одним image digest, mounts, user, capabilities, rootfs и network policy.

### Реализация

1. Запускать boundary probe внутри того же command container до первой
   Worker-команды и повторять после последней.
2. Создавать случайный judge sentinel вне всех mounts. Передавать его host path
   только как заведомо недоступную цель; дополнительно искать уникальное имя и
   случайное содержимое по всем видимым filesystem roots.
3. Контейнер shell-команд запускать без сети. LM Studio вызывается judge host,
   поэтому command container не требует `host-gateway` или bridge egress.
4. Применить `--read-only`, non-root UID, drop all capabilities,
   `no-new-privileges`, process/memory/time limits. Если pytest нужен temp,
   выделить scratch внутри sandbox и учитывать его в inventory.
5. Получать effective mounts, image digest, user, security options и network
   mode из runtime inspect; сравнивать с ожидаемой политикой. Declared tag не
   является достаточным attestation.
6. Probe проверяет:
   - sentinel/pack/checkout не читаются и не находятся;
   - запись возможна только внутри sandbox/scratch;
   - сеть полностью недоступна;
   - rootfs и runtime control paths недоступны на запись;
   - container identity не меняется между probe и Worker actions.

### Red tests

- Sentinel намеренно находится внутри mount под другим именем — probe обязан
  обнаружить leak. Это фиксирует прежний ложноположительный тест.
- Host path не существует в container, но тот же файл доступен через mount —
  результат leak, а не `blocked`.
- Probe с `network none`, Worker с bridge — attestation mismatch и fail.
- Mutable image tag меняет digest между probe/run; лишний mount; root user;
  writable rootfs; сохранённая capability; новый network interface.
- Реальный Worker-authored pytest пытается читать sentinel/pack, сканировать
  mounts, писать вне sandbox и открывать socket.

### Acceptance

- Все adversarial tests выполняются без skip в реальном runtime.
- Probe и Worker используют один container ID и одинаковую measured policy.
- Любое расхождение блокирует кампанию до release verdict.
- Сохранены Windows-host и POSIX-host/container результаты.

## QF-021 — полный независимый пересчёт T1–T8 из disk artifacts

- **Приоритет:** P0
- **Зависит от:** QF-019, QF-020
- **Исходный дефект:** schema и semantic validation пропускают report с
  неизвестной стадией, `context_peak_tokens=99999`, hallucinations/envelope
  violations > 0 и `verdict: pass`. Сейчас пересчитываются только correctness и
  `max_unique_files`.
- **Инвариант:** сохранённый report и manifest являются достаточным источником
  для независимого повторного расчёта каждого T1–T8 и итогового verdict без
  памяти процесса runner.

### Реализация

1. Создать единственный pure evaluator:
   `evaluate_artifact(report, thresholds, executor_attestation)`.
   Runtime и audit используют одну функцию, а не две расходящиеся реализации.
2. Пересчитывать из первичных disk fields:
   - T1 — stage checks;
   - T2 — точное множество и порядок `LIFECYCLE`, status каждой стадии;
   - T3 — stage retries и их сумма;
   - T4 — max полного input и framework tokens, только measured provenance;
   - T5 — max unique paths по call tool events;
   - T6 — классификация typed events и path resolution evidence;
   - T7 — envelope snapshots, writes, leash receipts, inventory и boundary;
   - T8 — полный обязательный defense evidence с receipts/hashes.
3. Не доверять сохранённым `totals`, `threshold_failures`, `process`,
   `correctness` и `verdict`: пересчитать и потребовать точного совпадения.
4. Добавить в per-run artifact thresholds source/revision/absolute snapshot и
   executor/image identity, либо криптографическую ссылку на manifest.
5. Manifest validator повторно загружает каждый report, сверяет commit, model,
   tokenizer, executor, thresholds revision и пересчитанные per-case medians.
6. NaN, infinity, boolean-as-number, duplicate events/stages/run IDs,
   отсутствующие receipts и несвязанные paths всегда дают fail.

### Red tests

- Сохранить точную ранее прошедшую mutation:
  `bogus stage + context 99999 + hallucinated 5 + envelope 4 + pass`.
- По одной mutation для каждого первичного и производного поля T1–T8.
- Totals ниже первичных calls/events; threshold failures очищены; verdict
  подменён; другой threshold revision; другой executor/image digest.
- Удалить или продублировать event, stage, receipt, report и run reference.

### Acceptance

- Каждая mutation отклоняется schema или semantic evaluator с точной причиной.
- Повторный audit по disk artifacts воспроизводит runtime verdict byte-for-byte.
- Synthetic 3x3 с одним failure сохраняет девять reports и даёт non-zero.
- Ни один `pass` нельзя получить изменением только производных полей.

## QF-022 — восстановить governance thresholds/tokenizer

- **Приоритет:** P1
- **Исходный дефект:** QF-015 добавил численный допуск `+48` в зафиксированный
  `thresholds.md` после implementation без maintainer Decision, хотя сам файл
  требует Decision для любого ослабления или ужесточения порога.
- **Инвариант:** численные release gates изменяются только заранее записанным
  maintainer Decision с основанием и новой revision.

### Реализация

1. Удалить непредрешённый `TOKENIZER_CONSISTENCY_ALLOWANCE = 48` и численный
   диапазон из release gate.
2. Сохранить обязательные независимые проверки:
   - completion возвращает measured full input usage;
   - tokenize endpoint возвращает measured framework token count;
   - tokenizer fingerprint стабилен в пределах кампании.
3. Правила host/tokenizer перенести в отдельный qualification host contract;
   `thresholds.md` оставить источником только утверждённых T1–T8.
4. Если численная consistency-проверка действительно нужна, остановиться на
   Human Gate: собрать evidence на reference host, предложить диапазон и создать
   maintainer Decision до изменения кода/порога.
5. Добавить governance test: изменение frozen thresholds revision без нового
   accepted Decision блокирует release tooling.

### Red tests

- Threshold file изменён, decision revision отсутствует/не accepted/создана
  после implementation.
- Код содержит численный release allowance, которого нет в accepted Decision.
- Tokenizer fingerprint drift и отсутствующие usage/tokenize measurements всё
  равно блокируют кампанию после удаления `+48`.

### Acceptance

- Нет неутверждённых численных gates.
- T4 остаётся measured и fail-closed.
- Любое будущее изменение thresholds имеет проверяемую цепочку Decision →
  revision → manifest.

## QF-023 — полное hash-покрытие asset bundle

- **Приоритет:** P1
- **Исходный дефект:** `__init__.py` обязателен в exact file set, но отсутствует
  в manifest hashes. Его подмена не обнаруживается. Symlink/junction rejection
  реализован, но не закреплён отдельной asset mutation-матрицей.
- **Инвариант:** каждый поставляемый regular/executable файл bundle, кроме самого
  manifest, имеет hash; ни один link/reparse point не принимается.

### Реализация

1. Включить `__init__.py` в manifest `files` или сделать пакетный marker
   статическим canonical asset с собственным hash.
2. `_verify_bundle` и `--check` сравнивают точное множество всех regular files,
   hashes и тип каждого filesystem entry.
3. На Windows проверять reparse attributes без зависимости только от строкового
   сравнения `realpath`; на POSIX использовать `lstat`/`is_symlink`.
4. Recovery проверяет target/prev/next новым полным validator до решения,
   какую копию восстановить.

### Red tests

- Подмена `__init__.py`; лишний executable; удалённый marker; изменённые
  permissions, если они часть контракта.
- Symlink на файл/каталог, junction/reparse point на Windows, broken link на
  POSIX, nested link и link с целью вне bundle.
- Crash recovery, где одна копия имеет корректный manifest, но подменённый
  `__init__.py`.

### Acceptance

- Любая mutation обнаруживается read-only `--check` и recovery validator.
- Hard-kill matrix остаётся зелёной на Windows и POSIX.
- Неуспешная проверка не удаляет последнюю валидную копию.

## QF-024 — восстановить provenance и durable evidence

- **Приоритет:** P1
- **Зависит от:** QF-019–QF-023
- **Исходные дефекты:** durable wheel manifest относится к commit `141c2ae`, а
  не Wave 2; QF-017 RESULT указывает alternate base `6267f84`, хотя parent в
  активной ветке — `6b44c66`; у QF-018 нет отдельного `RESULT.md`.
- **Инвариант:** каждый заявленный qualification result однозначно связан с
  фактической линейной историей и artifacts именно проверенного commit.

### Реализация

1. Не переписывать исторические RESULT незаметно. Добавить correction note с
   неправильным и правильным SHA и объяснением alternate commit.
2. Создать отдельный QF-018 `RESULT.md` со статусом `partial/not accepted`,
   точными проверками, skips и найденными дефектами.
3. После QF-019–QF-023 на чистом commit явно собрать wheel evidence заново.
   Manifest должен содержать текущий полный commit SHA, wheel hash, image digest,
   build frontend/backend и команды smoke.
4. Добавить checker ссылочной целостности RESULT files: parent/result SHA
   существуют, находятся в ancestry активной ветки и соответствуют пакету.
5. Release report различает historical evidence, current engineering evidence
   и pending reference evidence.

### Red tests

- Stale wheel commit; orphan/alternate base SHA; отсутствующий RESULT; artifact
  создан до проверяемого кода; SHA не находится в ancestry; dirty build tree.

### Acceptance

- Evidence checker проходит на всех QF-019–QF-024 artifacts.
- Durable wheel/image evidence относится к одному текущему clean commit.
- Исторические несоответствия явно сохранены как corrections, не замаскированы.

## QF-025 — повторная инженерная квалификация Wave 3

- **Приоритет:** P1
- **Зависит от:** QF-019–QF-024
- **Инвариант:** `engineering-passed` допустим только после live проверки той же
  изолированной среды и тех же artifacts, которые будет использовать QF-012.

### Обязательные проверки

1. Полный pytest; ни один skip не покрывает QF-019–QF-024 release guarantees.
2. Live command-container smoke на Windows host.
3. Полная QF-020 adversarial boundary matrix без skip на Windows host и
   выбранном POSIX host/runtime.
4. QF-021 T1–T8 disk mutation matrix и independent re-evaluation.
5. QF-022 threshold governance checker.
6. QF-023 asset mutation и hard-kill recovery matrix на Windows/POSIX.
7. PowerShell smoke, native POSIX smoke, wheel smoke, четыре layout/config
   validators на продукте из свежего wheel.
8. Explicit wheel/image evidence на проверенном commit.
9. Asset drift, legacy search и чистота дерева до/после.

### Acceptance

- Все обязательные проверки зелёные; skips ограничены необязательным PBT.
- Boundary report содержит measured container ID, image digest, mounts,
  non-root user, security options, network none и результаты двух probes.
- Disk re-evaluator воспроизводит все synthetic verdicts.
- `RESULT.md`, release report и backlog обновляются одним commit после pass.
- QF-012 остаётся `blocked` только LM Studio/reference runs, без инженерных
  блокеров.

## Порядок коммитов

1. `qualify: execute worker commands in pinned container` — QF-019.
2. `qualify: attest the effective command boundary` — QF-020.
3. `qualify: recompute T1 T8 from disk evidence` — QF-021.
4. `qualify: restore threshold governance` — QF-022.
5. `assets: hash every packaged bundle file` — QF-023.
6. `release: repair qualification provenance` — QF-024.
7. `release: record wave 3 engineering qualification` — QF-025.

## После Wave 3

Только после успешного QF-025 возобновляется QF-012:

1. LM Studio с `ornith-1.5-35b-a3b`, context 32768.
2. По три независимых чистых run M01, M02 и adversarial M03.
3. Все девять reports проходят schema, semantic re-evaluation и T1–T8.
4. Медианы correctness/process проходят неизменённые absolute thresholds.
5. Только затем DF3-009 и программа переводятся в `done`.
