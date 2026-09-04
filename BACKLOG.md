# Backlog

Unchecked items are active problems. Items marked `[x]` are verified as fixed.

## Completed v2 redesign

- [x] Separate product domains from finite artifact layers and route through a repository capability catalog.
- [x] Make Change the lifecycle container and typed Delta the output of analysis.
- [x] Split the workflow into Intake, Analyze, Specify, Decompose, Target, Implement, and Verify.
- [x] Make Route and Analyze iterative until Decision convergence.
- [x] Support implementation bugs with unchanged specification and Red-first evidence.
- [x] Keep product, architecture, integration, policy, and operational questions in `decisions/`.
- [x] Move tasks into their owning Change package and archive task history intact.
- [x] Keep canonical process files in the external, pinned DeltaFuse framework.
- [x] Add config/lock pinning, generated adapters, schemas, and validators.

## Review-01 v2

### Критические проблемы

- [x] Четыре канонических документа пусты (workflow.md 233 строки удалены, state-machine.md 89 строк удалены, roles.md и context-model.md созданы пустыми) — при этом docs/README.md и AGENTS.md объявляют их каноническими; фактически вся нормативная документация процесса теперь живёт только в proposal-документе на 1525 строк, который сам помечен как "rationale until replaced by a versioned specification". *(Review-02: все четыре документа восстановлены и наполнены — workflow.md, state-machine.md, roles.md, context-model.md.)*
- [x] Все содержательные шаблоны вычищены до 0 байт (16 файлов: AGENTS.md, DEC-0000-template, request.md, analysis.md, verification.md, spec-delta.md, TASK/SLICE, README всех директорий docs/, context.md, CHANGELOG) → installer кладёт пустышки в продукты; продукт получает пустой AGENTS.md, пустой docs/spec/README.md и т.д. Противоречит CHANGELOG ("Change templates" Added) и BACKLOG ("completed"). *(Review-02: все шаблоны восстановлены с содержательным контентом.)*
- [x] Migration guide удалён (коммит "Remove legacy migrations directory"), но на него ссылаются README.md, docs/using.md, AGENTS.md (mandate migrations/**), CHANGELOG. Процесс апгрейда v1→v2 теперь недокументирован, при этом -Force требует "review the migration guide". *(Review-02: все ссылки на migration guide удалены из README, using.md, AGENTS.md; CHANGELOG переписан под 2.0.0; -Force теперь требует только проверки версий активных Changes.)*
- [x] Латентный баг пиннинга версий: config-шаблон жёстко содержит version: 2.0.0; installer обновляет её только при -Force; любой бамп VERSION без правки шаблона → свежая установка проходит, но validate-layout падает на несоответствии config vs lock. *(Review-02: оба инсталлятора получили логику configExisted — при свежей установке версия в config перезаписывается реальной версией из VERSION.)*

### Несоответствия и рассинхрон документации

- [x] AGENTS.md: mandate ссылается на docs/process/, skills/, schemas/, templates/, validators/, migrations/ — фактические пути после реорганизации: docs/*.md, process/skills, process/schemas, process/templates, tests/ (validators), migrations удалён. *(Review-02: mandate обновлён на актуальные пути.)*
- [x] AGENTS.md Verification: табличная коррупция путей "	ests/smoke-test.ps1" (символ \t съел "\t" из "\tests") — команды невоспроизводимы; шаг 3 дублирует шаг 2. *(Review-02: коррупция устранена, команды корректны, дублирующий шаг удалён.)*
- [x] CLAUDE.md: те же устаревшие пути + усечённый lifecycle без Converge/Archive. *(Review-02: пути и lifecycle приведены в соответствие.)*
- [x] README.md: дерево пакета со старыми путями (docs/process/, skills/, schemas/, templates/, migrations/) и битые ссылки (docs/process/README.md, migrations/v1-to-v2.md). README.ru.md: пустая ссылка v1 -> v2. *(Review-02: дерево пакета обновлено, битые ссылки заменены на рабочие.)*
- [x] Языковая мешанина: docs/README.md и docs/using.md только на русском, тогда как README.md/AGENTS/skills — английские; англоязычный README ведёт на русскоязычный docs/README.md. *(Review-02: docs/README.md и docs/using.md переведены на английский, добавлены README.ru.md и using.ru.md с переключателями языков.)*
- [x] CHANGELOG: v2-редизайн числится в [Unreleased], но VERSION=2.0.0 и BACKLOG называет редизайн завершённым; также CHANGELOG заявляет migration guide как Added, а он удалён в HEAD. *(Review-02: редизайн оформлен как [2.0.0] - 2026-09-04, пункт про migration guide удалён.)*

### Пробелы процесса и модели

- [x] Нет схем для routing.yaml, coverage.yaml, slices/*.md, spec-delta — при том, что change/task/decision/evidence/capability имеют JSON Schema; верификаторы не проверяют их вообще (validate-layout проверяет только наличие change.yaml/request.md, не структуру). *(Review-02: схемы routing/coverage/slice/spec-delta добавлены в process/schemas/; шаблоны slices/SLICE-01.md и spec-delta.md получили YAML frontmatter; validate-layout.ps1 и validate-layout.sh расширены структурной валидацией _capabilities.yaml, change.yaml, routing.yaml, coverage.yaml, slices, tasks и decisions.)*
- [x] Evidence phase enum содержит regression и verification, но процесс не определяет, где живут эти evidence (layout показывает только evidence/, скиллы пишут только red/ и green/); verification-evidence требует task ID, хотя верификация — уровень Change.
- [x] Decision schema требует change (CHG-*) *(Review-02: decision.schema.yaml обновлён — поле change убрано из обязательных и поддерживает null для глобальных и Bootstrap-решений; документация синхронизирована)*, но Bootstrap и глобальные политики предполагают решения вне конкретного Change.
- [x] Статусная модель Change (18 статусов) нигде не описана: state-machine.md пуст; переходы (например, specification-proposed → specified, кто и когда ставит blocked-on-decision / duplicate / superseded) заданы только неявно в скиллах; часть статусов (duplicate) вообще не упоминается ни одним скиллом. *(Review-02: state-machine.md описывает полную таблицу переходов Change, slice, task и Decision, включая duplicate/superseded и gate-условия.)*
- [x] Инсталлятор хардкодит корни адаптеров (.agents/.cursor/.gemini) вместо чтения adapters.roots из config.yaml — поле конфига фактически мертво. *(Review-02: init.ps1, init.sh, validate-layout.ps1 и validate-layout.sh динамически парсят adapters.roots из .deltafuse/config.yaml, используя fallback на дефолты только при отсутствии секции; кастомизация корней протестирована)*
- [x] Статусная машина task: verify-change скилл пишет "all tasks are terminal", но verify-change не меняет статусы задач на verified (нет шага); implement ставит implemented; кто ставит verified — не сказано. *(Review-02: workflow.md §7 и state-machine.md явно назначают перевод задач в verified этапу Verify; см. Review-02 ниже про отставание SKILL.md.)*

### Мелочи/гигиена

- [x] .gitignore — шаблонный Java-мусор (*.jar, hs_err_pid), не относящийся к репозиторию. *(Review-02: .gitignore очищен от Java-мусора и адаптирован под shell/Python/IDE/OS).* 
- [x] CHANGELOG ссылается на keepachangelog 1.0.0 (текущая 1.1.0) — мелочь. *(Исправлено: обновлено на 1.1.0 в CHANGELOG.md и шаблоне).* 
- [x] Инсталлятор копирует пустые README в продукты → пользователям непонятно назначение директорий. *(Review-02: README-шаблоны наполнены.)*
- [x] Двойной источник правды по путям: skills говорят "paths shown below are defaults" и ссылаются на config, но при этом validate/skills используют буквальные docs/... — рассинхрон при кастомизации paths.* в конфиге (валидатор вообще не читает config paths и требует фиксированные docs/...). Это серьёзнее мелочи: если продукт переопределит paths.changes, валидатор завалит его. *(Review-02: validate-layout.ps1 и validate-layout.sh считывают paths.* из .deltafuse/config.yaml и валидируют структуру по настроенным путям)*

## Review-02 (проверка после восстановления)

Состояние на коммит c36acb1 "fix inconsistency" (плюс незакоммиченные BACKLOG.md и 4 новые схемы routing/coverage/slice/spec-delta в process/schemas/).

### Подтверждено исправленным

См. отметки `[x]` в Review-01 выше: восстановлены все канонические документы и шаблоны, убраны ссылки на migration guide, исправлен баг пиннинга версий (configExisted-логика в обоих инсталляторах), обновлены пути в AGENTS.md/CLAUDE.md/README, устранена таб-коррупция в Verification, docs/README.md и docs/using.md переведены на английский с добавлением README.ru.md / using.ru.md, CHANGELOG оформлен как [2.0.0], state-machine.md описывает полную таблицу переходов, устранена асимметрия source между lock.yaml и config.yaml с валидацией в validate-layout.

### Осталось активным из Review-01

- [x] validate-layout не валидирует структуры артефактов (change.yaml, task frontmatter, evidence) ни по одному из 9 schema-файлов — проверяется только наличие change.yaml/request.md. Новые схемы routing/coverage/slice/spec-delta также не подключены ни к какому валидатору.
- [x] evidence.schema.yaml: фазы `regression` и `verification` по-прежнему не имеют определённого места в layout *(Исправлено: task сделан опциональным/null для verification, определены пути evidence/red/, evidence/green/, evidence/regression/ и evidence/verification/run.yaml)* — скиллы пишут только evidence/red/ и evidence/green/; regression свёрнут в green evidence, verification существует только как verification.md без YAML-артефакта.
- [x] decision.schema.yaml: поле `change` обязательное — глобальные/Bootstrap-решения без Change невозможны. *(Исправлено: change убрано из required, разрешён null для Bootstrap и глобальных политик)*
- [x] Инсталляторы хардкодят корни адаптеров (.agents/.cursor/.gemini) вместо чтения adapters.roots из config.yaml — поле конфига фактически мертво. *(Исправлено в init.ps1/init.sh/validate-layout)*
- [x] .gitignore — Java-шаблонный мусор. *(Исправлено)*
- [x] Двойной источник правды по путям (config paths.* vs буквальные docs/... в валидаторе и скиллах). *(Исправлено: валидаторы динамически считывают paths.* из config.yaml)*

### Новые проблемы (несоответствия в восстановленных документах)

- [x] state-machine.md «Инвариант версионирования»: пример фиксирует `schema_version: 1` *(Исправлено: обновлено на schema_version: 2)* в change.yaml — противоречит change.schema.yaml (`schema_version: const 2`) и шаблону change.yaml (schema_version: 2). Живой Change, оформленный по примеру из канонического документа, не пройдёт валидацию схемой.
- [x] context-model.md: пример каталога `_capabilities.yaml` структурно противоречит capability.schema.yaml — `schema_version: 1` вместо const 2; плоская структура (title/responsibility/excludes/actors/entities/events/status,顶层-level ключи `capabilities:` и `policies:`) вместо вложенной `domains.<id>.capabilities.<id>` со полями summary/spec; поля title, responsibility, excludes, actors, entities, events, status отсутствуют в схеме. *(Review-02: пример каталога в context-model.md приведён в строгое соответствие с capability.schema.yaml — schema_version: 2, вложенная структура domains.<id>.capabilities.<id> со свойствами summary, spec, policies, code_roots, test_roots, depends_on)*
- [x] roles.md «Уровни оркестрации» ссылается на несуществующие скиллы `/bootstrap`, `/change`, `/fix-bug` — в process/skills/ только 7 примитивов; составные entry points нигде не определены и не генерируются инсталлятором. *(Review-02: раздел «Уровни оркестрации» в roles.md переписан — убраны фиктивные команды, зафиксированы 7 канонических примитивов и профили исполнения)*
- [x] verify-change/SKILL.md не обновлён под восстановленную модель *(Исправлено: добавлен шаг перевода реализованных задач в verified)*: не содержит шага перевода задач в `verified` (workflow.md §7 и state-machine.md его требуют) и противоречит им, оперируя только «terminal task states».
- [x] Четыре канонических документа (workflow.md, state-machine.md, roles.md, context-model.md) существуют только на русском, тогда как весь остальной фреймворк (README, AGENTS.md, skills, schemas, templates) англоязычный; docs/README.md рекламирует пару English|Русский, но для этих четырёх документов русской версии нет — наоборот, английской нет. *(Review-02: все 4 канонических документа переведены на английский как канонические источники; созданы двуязычные пары *.ru.md с переключателями языков; docs/README.md и docs/README.ru.md обновлены).* 


## Review-03

### А. Восстановленный `docs/workflow.md` противоречит и proposal, и собственным схемам

- [x] **Typed Delta искажён** (критично). Workflow §2 «Pass B» определяет дельту по 5 слоям: `spec`, `architecture`, `contract`, `test`, `code` со значениями `unchanged`/`decision-required`. Proposal (L505–522) и `change.schema.yaml` задают **7 проекций** (`specification`, `catalog`, `decisions`, `tasks`, `tests`, `implementation`, `evidence`) с операциями `none|add|modify|remove|mixed|derive|propose|supersede|record`. Ни `unchanged`, ни `decision-required` в enum схемы нет; слои `architecture`/`contract` не существуют. Плюс skill `analyze-change` перечисляет 7 проекций — workflow расходится со всеми. *(Исправлено: workflow.md, workflow.ru.md, roles.md приведены в строгое соответствие со схемой change.schema.yaml — зафиксированы 7 нормативных проекций дельты specification, catalog, decisions, tasks, tests, implementation, evidence и их допустимые операции)*.
- [x] **Пример task-frontmatter невалиден** (§4): поля `title`, `test_target`, `test_oracle` отсутствуют в `task.schema.yaml` (`additionalProperties: false`), а обязательные `requirement_delta`, `spec_refs`, `allowed_paths`, `forbidden_paths` в примере пропущены. *(Исправлено: пример frontmatter в workflow.md и workflow.ru.md приведен в точное соответствие со схемой task.schema.yaml; поля Outcome, Test Oracle, Unchanged Behavior и Verification размещены в теле Markdown в соответствии с шаблоном задачи)*.
- [x] **Пример Red-evidence неверен** (§5): `status: passed`, `test_target`, `output_summary` — не существуют в `evidence.schema.yaml`; семантическая ошибка: Red должен быть `result: expected-failure`, а не «passed». *(Исправлено: пример Red-evidence в workflow.md приведен в полное соответствие с evidence.schema.yaml — установлены command, timestamp, exit_code, result: expected-failure, failure_category, summary, changed_paths и spec_status; в описании Implement зафиксированы фазы green/regression с result: passed)*.
- [x] **Bootstrap: `project.baseline: active`** — противоречит `accepted` в proposal (L231), шаблоне `config.yaml` и `docs/using.md`. *(Исправлено: значение переведено в accepted в workflow.md, roles.md и roles.ru.md в соответствии со схемой, шаблоном config.yaml и using.md)*.
- [x] **Нумерация claims `CR-01`** — противоречит паттерну `^CR-[0-9]{3,}$` в `slice.schema.yaml` и шаблону request (`CR-001`). *(Исправлено: в workflow.md нумерация claims приведена к каноническому 3-значному формату CR-001 в соответствии со схемой slice.schema.yaml и шаблоном request.md)*.
- [x] **Архивация без date-префикса**: workflow §7 пишет `docs/archive/changes/<change-id>`, тогда как proposal (L1182), skill verify-change и state-machine — `<date>-<change-id>`. *(Исправлено: в workflow.md и state-machine.md путь перемещения пакета в архив синхронизирован с форматом docs/archive/changes/<date>-<change-id> в соответствии с proposal, skill verify-change и state-machine.ru.md)*.

### Б. Восстановленный `docs/state-machine.md`

- [x] **Bug-путь пропускает Decompose**: переход `analyzed → targeting (spec unchanged)` противоречит proposal (bug flow явно включает «Decompose from spec refs + reproduction», L1200) и workflow.md §Bug Workflow (шаг 4 «Decompose creates bugfix task»). Без Decompose задачи вообще не существуют — переход нереализуем. *(Исправлено: в state-machine.md и workflow.md bugflow выровнен: analyzed переходит в specified с фиксацией доказательства неизменности спеки в spec-delta.md, затем через decompose-change создаются задачи TASK-NNN в состоянии decomposed, и только затем запускается target-task)*.
- [x] **`not-reproduced` висит**: статус объявлен терминальным в таблице, но в mermaid-диаграмме нет ни одного входящего перехода, и в таблице не указано, из каких состояний он достижим (proposal: терминал после Red-попытки). *(Исправлено: в state-machine.md и state-machine.ru.md в диаграмму и таблицы переходов добавлены явные входы в терминальное состояние not-reproduced из analyzing, targeting и verifying с фиксацией диагностического evidence/отчета)*.

### В. Схемы vs модель proposal

- [ ] **`capability.schema.yaml` v2 обеднёл метамодель**: proposal требует минимальные routing-поля capability — `responsibility`, `excludes`, `actors`, `entities`, `events`, lifecycle `status` (L612–619) — и верхнеуровневый каталог `policies` с `applies_to` (L604–609). Схема с `additionalProperties: false` **жёстко запрещает** все эти поля и каталог политик. Инвариант 23 («cross-cutting policies загружаются по routing rules») остаётся без носителя: policy теперь лишь строка в списке у capability, само определение политики в каталоге не живёт.
- [ ] **`slice.schema.yaml`** не допускает `policies` и `spec_refs` во frontmatter (`additionalProperties: false`), хотя proposal требует их в контракте слайса (L800–812).
- [ ] **`coverage.schema.yaml`**: `claims.evidence` содержит `red`/`green`/`verification`, но **не `regression`** — при том, что regression-evidence теперь обязательна (workflow §6, state-machine, skill implement-task). Новый фикс ввёл четвёртую фазу, но в coverage она не отражена.

### Г. Отклонения от плана proposal, не зафиксированные как решения

- [ ] **Удалены entry points `/bootstrap`, `/change`, `/fix-bug`** из roles.md (фикс Review-02 легитимен — команд не существовало), но migration-план proposal (шаг 25: «После стабилизации primitives добавить /bootstrap, /change, /fix-bug orchestrators») прямо их предусматривает. Отклонение разумно (незадокументированные сущности хуже), но нигде — ни в CHANGELOG, ни в BACKLOG — не записано как осознанный отказ от пункта плана. L1391 proposal: «Оркестратор может провести несколько логических шагов одной командой» — семантика частично сохранена «Execution Profiles», формальная — потеряна.
- [ ] **Пример `change.yaml` из proposal невалиден** текущей схемой (ключи `spec_delta`/`design` отвергаются `additionalProperties: false`). Это корректная эволюция (proposal заменён схемой), но при чтении archive/proposal как «baseline» это надо знать.
- [ ] **`context-model.md`**: Pass B выводит `spec-delta.md` — по proposal и workflow spec-delta создаётся на **Specify**, Analyze его не пишет (L890–897). Рассинхрон в восстановленном документе.
