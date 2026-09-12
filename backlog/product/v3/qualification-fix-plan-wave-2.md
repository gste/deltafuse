# DeltaFuse 3.0 — qualification fix plan, wave 2

- **Статус:** `ready`
- **Основание:** независимая проверка исполнения QF-001–QF-012, 2026-09-13
- **Предыдущая волна:** [qualification-fix-plan.md](qualification-fix-plan.md)
- **Цель:** закрыть оставшиеся fail-open границы qualification до реальных
  прогонов QF-012 на Worker класса 35B A3B с окном от 32k
- **Baseline v2:** не используется

Первая волна сохраняется как история реализации. Этот файл — отдельная живая
очередь исправлений QF-013–QF-018. Каждый пакет должен помещаться в ограниченный
контекст слабой LLM: один основной инвариант, перечисленные входные файлы, один
Red-набор и один проверяемый результат.

До успешного QF-018 статус release qualification остаётся
`engineering-failed / correction wave 2`. QF-012 не возобновляется раньше
QF-018 и доступности reference LM Studio host.

## Подтверждённое основание

Независимая проверка commit `789f5cb` установила:

- полный suite зелёный: `449 passed, 1 skipped`;
- PowerShell и Git Bash smoke прошли, asset drift отсутствует;
- официальный reference probe корректно вернул `PENDING`, exit 2;
- при этом staging не закрывает host filesystem от Worker-authored pytest;
- T2 принимает восемь или семь произвольных стадий;
- T4 использует потенциально занижающий fallback `chars // 4`;
- recovery asset bundle может удалить единственную предыдущую копию после
  аварии между rename;
- schema допускает неполные per-call measurements;
- QF-012 не выполнен, а живой backlog всё ещё помечает первую волну `ready`.

## Общие правила исполнения

1. Один пакет — один reviewable commit с кодом, тестами и собственным
   `RESULT.md`.
2. Сначала сохранить Red evidence на текущем поведении, затем Green и полный
   regression result. Тест, проходивший до исправления, не считается Red.
3. Нельзя ослаблять T1–T8, менять reference model/context или подменять
   отсутствующее измерение оценкой, способной дать pass.
4. Release verdict строится только из disk artifacts, прошедших schema и
   semantic validation.
5. После каждого пакета дерево должно быть чистым. Генерируемое release evidence
   создаётся только явной командой.
6. Описания `RESULT.md` не заменяют воспроизводимые тесты и сохранённые outputs.

## QF-013 — обязательная системная изоляция Worker

- **Приоритет:** P0
- **Исходный дефект:** `StagingRoot` меняет cwd/env, но разрешённый
  `python -m pytest` исполняет Worker-authored код с правами runner. Исходный
  checkout и judge pack остаются читаемыми по абсолютному пути или через поиск
  filesystem. Текущий threat model объявляет это допустимым, хотя acceptance
  QF-004 требовал обратного.
- **Инвариант:** release qualification не запускает Worker-код на машине/в
  namespace, где видны judge pack, framework checkout или произвольные host
  files. Единственный writable root Worker — sandbox конкретного run.

### Реализация

1. Ввести интерфейс `QualificationExecutor` с режимами:
   - `isolated` — обязательный для release/reference campaign;
   - `local-dev` — только для разработки, всегда делает итоговый verdict
     `non-release` и не может создать release manifest с `pass`.
2. Реализовать `isolated` через контейнер/VM/отдельный machine boundary:
   - внутрь передаются wheel DeltaFuse, pytest и sandbox одного run;
   - judge pack и framework checkout не монтируются;
   - sandbox монтируется read/write, остальные mounts read-only либо отсутствуют;
   - сеть разрешена только к явно заданному локальному LM Studio endpoint;
   - scoring выполняется judge-side после возврата sandbox.
3. Сохранять в manifest attestation границы: executor kind, image/VM identity,
   mounts, network policy и provenance каждого поля.
4. Удалить из threat model утверждение, что доступ к host filesystem приемлем
   для release qualification. L1 staging оставить только как local-dev helper.
5. Если isolated executor недоступен, завершать кампанию `PENDING` до первого
   Worker-вызова и не создавать release-pass artifacts.

### Red tests

- Worker-authored pytest пытается прочитать sentinel за пределами sandbox по
  известному абсолютному пути — чтение невозможно.
- Тест ищет `process/bench/cases`, `hidden_suite` и `oracle` вверх по дереву и
  по доступным mount roots — ничего не находит.
- Тест пытается создать файл рядом с sandbox, в temp/home и framework checkout —
  ни один файл не появляется.
- Попытка сетевого обращения не к LM Studio endpoint отклоняется.
- `local-dev` с зелёным scorecard не может дать release verdict `pass`.

### Acceptance

- Adversarial integration выполняется внутри фактической release boundary, а
  не через monkeypatch.
- Judge-side sentinel и pack недоступны на чтение; вне sandbox нет изменений.
- Manifest доказывает isolated mode. Отсутствие доказательства даёт fail/PENDING.
- Windows host и выбранный POSIX/container runtime имеют сохранённые результаты.

## QF-014 — точный T2 и lifecycle medians

- **Приоритет:** P0
- **Исходный дефект:** `completed < 7` принимает восемь стадий и не проверяет
  имена. Семь произвольных стадий также могут пройти. Median evaluation не
  применяет отдельные correctness/process assertions.
- **Инвариант:** T2 проходит только для точного lifecycle
  `Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`,
  где каждая стадия присутствует ровно один раз и имеет `completed`.

### Реализация

1. Вынести канонический ordered tuple lifecycle в один модуль/контракт Core.
2. Нормализовать scorecard stage representation без потери порядка.
3. Проверять точное равенство имён и порядка, отсутствие duplicate/extra,
   status `completed`, отсутствие skipped/aborted.
4. Считать process только из валидного канонического множества; значение не
   может быть меньше 0 или больше 100.
5. Явно применять thresholds к median correctness и median process, даже если
   все per-run verdicts уже проверены.

### Red tests

- 8 completed stages; 7 произвольных; duplicate Verify; отсутствующий Analyze;
  переставленные стадии; skipped/aborted; неизвестный статус.
- Mutation каждой строки канонического lifecycle меняет verdict на fail.
- Median correctness/process: missing, ниже порога, NaN/boolean и выше 100.

### Acceptance

- Только точные семь стадий в правильном порядке дают T2 pass.
- Все мутации дают диагностическое сообщение с ожидаемым и фактическим stage.
- Per-run и median correctness/process отражены в report/manifest и проверены.

## QF-015 — fail-closed tokenizer и T4 provenance

- **Приоритет:** P0
- **Исходный дефект:** при отсутствии/ошибке host tokenizer runner использует
  `framework_chars // 4`. Эта оценка может занижать токены и дать ложный pass,
  а fallback маркируется как `measured`.
- **Инвариант:** release verdict `pass` возможен только при измеренном полном
  input usage и измеренном framework-controlled input совместимым tokenizer.

### Реализация

1. Разделить состояния token measurement:
   `measured`, `estimated-nonrelease`, `unavailable`, `error`.
2. Для reference campaign требовать рабочий host tokenize endpoint и валидный
   token sequence/count. HTTP 404, timeout, connection error и garbage одинаково
   блокируют release qualification до Worker-вызова.
3. Удалить `chars // 4` из threshold-bearing release metrics. Допустить оценку
   только в local-dev diagnostics с provenance `estimated`, без права pass.
4. Проверять tokenizer fingerprint до и после campaign; изменение делает
   кампанию недействительной.
5. Проверять согласованность diagnostic completion usage и tokenizer на
   калибровочном тексте в документированном допустимом диапазоне.

### Red tests

- Endpoint absent/404/timeout/500/garbage/negative count/boolean count.
- Unicode, русский текст, emoji и code-heavy input, где `chars // 4` занижает
  фактическое число токенов.
- Fingerprint меняется между runs.
- Metrics с `estimated` или `unavailable` пытаются пройти T4.

### Acceptance

- Ни один release report с не-measured tokenizer provenance не получает pass.
- T4 хранит метод, endpoint identity, fingerprint и точное измеренное значение.
- Full input usage и framework subset измеряются fail-closed отдельно.

## QF-016 — crash-safe asset transaction

- **Приоритет:** P1
- **Исходный дефект:** swap выполняет `assets -> prev`, затем `next -> assets`.
  При hard crash между rename target отсутствует, а следующий запуск
  `_cleanup_stale` безусловно удаляет `assets.prev-*` — единственную целую копию.
- **Инвариант:** после сбоя в любой точке следующий запуск восстанавливает либо
  предыдущий валидный bundle, либо полностью проверенный новый; единственная
  валидная копия никогда не удаляется.

### Реализация

1. Добавить transaction journal в sibling directory: id, target, prev, next,
   phase и hashes manifest. Обновлять journal атомарной заменой файла.
2. На startup сначала выполнять recovery, затем cleanup:
   - valid target есть — удалить только подтверждённые stale copies;
   - target отсутствует, valid prev есть — восстановить prev;
   - target отсутствует, valid next есть и journal разрешает commit — завершить;
   - неоднозначное/невалидное состояние — остановиться без удаления.
3. `_verify_bundle` проверяет schema manifest, точное множество файлов, hashes и
   отсутствие symlink/junction внутри bundle.
4. Документацию называть `crash-safe transactional replacement`; не заявлять
   single-operation atomic directory replacement там, где Windows её не даёт.

### Red tests

- Отдельный subprocess принудительно завершается после каждой фазы transaction,
  включая промежуток между rename. Затем новый process запускает recovery.
- Несколько prev/next, повреждённый journal, невалидный target, valid prev,
  extra packaged file и symlink/junction.
- Проверяется byte-for-byte hash дерева до сбоя и после recovery.

### Acceptance

- Hard-kill matrix проходит на Windows и POSIX.
- После recovery `sync_assets.py --check` возвращает 0.
- Нет состояния, в котором cleanup удаляет последнюю валидную копию.

## QF-017 — строгие report/manifest schemas и semantic validation

- **Приоритет:** P1
- **Исходный дефект:** `calls.items` допускает любой object; обязательные поля
  T4–T7 не проверяются. Верхнеуровневые результаты и breakdown-структуры также
  частично необязательны, `additionalProperties: true` скрывает drift формата.
- **Инвариант:** schema-valid release artifact содержит все данные, необходимые
  для независимого пересчёта T1–T8; semantic validator подтверждает связи между
  полями, runs, cases и verdicts.

### Реализация

1. Описать строгие `$defs` для stage, call, tool event, totals, model attestation,
   run reference и case verdict; закрыть их `additionalProperties: false`.
2. Для каждого call требовать input tokens, framework tokens/provenance,
   unique files, hallucinated paths и envelope violations с корректными типами.
3. Разделить `pass/fail measured report` и `failure report` через `oneOf`:
   - pass: measurements non-null, error отсутствует, threshold failures пусты;
   - fail измеренный: measurements присутствуют, failures непусты;
   - infrastructure failure: error обязателен, nullable measurements допустимы.
4. Добавить semantic validation после JSON Schema:
   - totals пересчитываются из calls/stages/events;
   - ровно заявленное число уникальных run IDs и case IDs;
   - каждый manifest run ссылается на существующий schema-valid report;
   - verdict manifest равен пересчитанному verdict;
   - commit/model/threshold revision одинаковы во всех artifacts.
5. Писать manifest только после успешной schema+semantic validation временной
   версии; partial failure сохранять как отдельный валидный state.

### Red tests

- `calls: [{}]`; отсутствующее поле каждого T4–T7 measurement; лишнее поле;
  строка/boolean/NaN вместо числа; inconsistent totals.
- Pass с `null`, pass с error, fail без failures, duplicate run ID, отсутствующий
  report, несовпадающий commit/model/revision, подменённый verdict.
- Mutation test каждого обязательного поля disk format.

### Acceptance

- Неполный или противоречивый artifact не записывается как release evidence.
- Все T1–T8 можно пересчитать только из сохранённых файлов без памяти процесса.
- Synthetic campaign 3x3 с одним failure сохраняет все результаты и даёт
  ненулевой exit; mutation matrix полностью зелёная.

## QF-018 — повторная независимая инженерная квалификация

- **Приоритет:** P1
- **Зависит от:** QF-013–QF-017
- **Инвариант:** статус `engineering-passed` возвращается только после проверки
  новой системной boundary и всех mutation/crash/schema regressions на чистом
  commit.

### Проверки

1. Полный pytest с точными counts и обоснованием каждого skip.
2. QF-013 adversarial run в фактическом isolated executor.
3. QF-014 mutation matrix точного lifecycle и median thresholds.
4. QF-015 live tokenizer probe и негативная matrix отсутствующих измерений.
5. QF-016 hard-kill recovery matrix в отдельных процессах.
6. QF-017 schema/semantic mutation matrix и synthetic 3x3 campaign.
7. PowerShell smoke, Git Bash/POSIX smoke, wheel smoke, explicit wheel evidence.
8. Все четыре layout/config validators на чистом wheel-продукте.
9. Asset drift, legacy runtime search и Git-чистота до/после.

### Acceptance

- Все обязательные проверки зелёные; skips не покрывают release guarantees.
- Сохранены platform, версии, полный commit SHA, точные команды и outputs.
- Release report и backlog обновлены одним commit только после pass.
- QF-012 остаётся `blocked`, пока нет LM Studio и девяти реальных runs.

## Порядок коммитов

1. `qualify: require isolated release executor` — QF-013.
2. `qualify: enforce exact lifecycle completion` — QF-014.
3. `qualify: require measured tokenizer for release` — QF-015.
4. `assets: recover interrupted bundle transactions` — QF-016.
5. `qualify: validate complete campaign artifacts` — QF-017.
6. `release: record wave 2 engineering qualification` — QF-018.

QF-013–QF-015 — блокирующая последовательность. QF-016 можно выполнять
параллельно ей, но QF-017 должен учитывать итоговые поля QF-013 и QF-015.
QF-018 запускается только после объединения всех пяти исправлений.

## После wave 2

После успешного QF-018 возобновляется существующий QF-012:

1. LM Studio с `ornith-1.5-35b-a3b`, context 32768.
2. Три чистых запуска M01, три M02 и три adversarial M03.
3. Каждый run и медианы correctness/process проходят T1–T8.
4. Публикуются все девять reports и campaign manifest.
5. Только после этого DF3-009 и программа могут перейти в `done`.
