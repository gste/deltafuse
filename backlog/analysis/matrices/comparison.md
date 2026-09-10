# Сравнение аналогов с DeltaFuse (A11)

Дата старта: 2026-09-08. Карточки A11-02+ **дописывают** секции, не переписывая решения A11-01 без новой evidence.

Формат плана A11: проблема → механизм аналога → первичное evidence → эквивалент DF → выгода → цена → риск → решение. Решения: **сохранить своё** / **адаптировать** / **исследовать** / **не переносить** / **упростить/удалить своё**. Популярность ≠ proof. Копирование ресурсов — только после лицензии.

Пакетный путь `analysis/matrices/contracts.md` нет; строки DF — [backlog/matrices/contracts.md](../matrices/contracts.md) (ANA-01/02, SPC-01/06).

Живой LLM-ранг аналогов vs ornith: **not-tested** ([A11-06](../experiments/A11-06/result.md) — нет first-class интеграции с `:1240`). A10-01 уже показал, что минимальный SDD на том же SUT не замена ядра. Качество Copilot/Claude/Opus/Kiro **не** ранжировать против ornith.

---

## Spec Kit (A11-01)

Один механизм: цепочка **constitution → specify → plan → tasks → implement → converge** (plus optional clarify/analyze/checklist) как альтернатива Change FSM. Конституция и extensions — адаптация процесса, не второй эксперимент.

Pin: release **v1.0.4** (2026-09-02), commit `cb610277fdea781fcfa83d20522c2db37c94068d`. Источники: [experiments/A11-01/sources.md](../experiments/A11-01/sources.md). Лицензия: **MIT** (GitHub, Inc.) — шаблоны копировать можно только с notice; A12 всё равно не копирует без отдельного решения.

| ID | Проблема DF | Механизм Spec Kit | Evidence | Эквивалент DF | Выгода | Цена (контекст / ops) | Риск | Решение |
|---|---|---|---|---|---|---|---|---|
| SK-01 | A10-01: SDD даёт файлы на S05, не качество; FSM/Change дороги | Slash/skills: specify→plan→tasks→implement; цикл implement/converge до «Converged» | SK-R1 | Intake → Analyze → Specify → Decompose → Implement → Verify/Archive ([A02-10](../experiments/A02-10/result.md)) | Меньше YAML-гейтов, привычный markdown | Много markdown в одном feature dir; нет `context_budget` слайса ([A03-05](../experiments/A03-05/result.md)) | Потеря provenance Change; F-010-класс «есть текст — значит specified» | **не переносить** как замену ядра. A11-06 не ранжировать, если нет той же модели |
| SK-02 | Q-001: ширина борозды и принципы проекта не в lock; skills жёсткие | `/speckit.constitution` + `memory/constitution.md`; plan сверяет principles; статьи IV–VI — слоты проекта | SK-R1, SK-D3 | `docs/spec/context.md`, `.deltafuse/lock.yaml`, `AGENTS.md` | Один раз задать non-negotiables без раздувания каждого skill | Constitution в каждом plan/analyze — токены (A03-04: budget считает файлы, не полный prompt) | Immutable articles I–III (library-first, CLI, TDD) чужды DF Change-пакету | **исследовать** в A12-04 ([Q-007](../parking/design-questions.md)). Не патчить skills |
| SK-03 | Decompose: DAG, `TASK-*`, `allowed_paths` (DEC-01/02) | `tasks.md` из `plan.md` (+ optional data-model/contracts/research) | SK-D1 | `tasks/TASK-*.md` + `task.schema.yaml` + `fsm.py` topo-sort | Проще список для агента | Нет схемы/цикла/oracle на задаче | Свободный markdown обходит DEC-02 | **сохранить своё** typed tasks. Не заменять `tasks.md` |
| SK-04 | Verify редко; hidden suite ловит ложный Green (F-009, A10-01) | `/speckit.converge`: агент сверяет код со spec/plan/tasks и дописывает remaining tasks | SK-R2 | Verify + independent hidden/pytest ([A09-13](../experiments/A09-13/result.md), A10-01) | Явный loop «пока не Converged» | Converge = оценка той же модели | Самооценка remaining ≠ oracle | **сохранить своё** независимый oracle. Loop «до сходимости» **не переносить** без внешнего гейта |
| SK-05 | S04: вилка должна стоить Human Gate (ANA-02, AB-06) | `/speckit.clarify` *рекомендован* до plan, не FSM-блок | SK-R2 | `DEC-* proposed` → `blocked-on-decision` | Clarify дешевле, чем полный DEC | Агент может пропустить clarify | Скрытые допущения (SPEC-002) | **сохранить своё** human gate. Clarify как extra **исследовать** только если не снимает блок |
| SK-06 | F-010 / SPC-06: `specified` = файл spec-delta, не live spec | Шаблоны spec/plan с чеклистами; `/speckit.analyze` после tasks; `/speckit.checklist` | SK-D2, SK-R2 | SPC-01 якоря; ANA-01 coverage; слабый SPC-06/F-010 | Чеклист «дыр в тексте» | LLM self-review, не `check_gate` | Чеклист зелёный при пустых путях (как F-010) | **сохранить своё** FSM. Усилить `specified` в A12 (**исследовать**). Чеклисты в prompt — не замена гейта |
| SK-07 | Процесс один на все модели (Q-001) | Extensions / presets / bundles; bug и assess opt-in | SK-R3 | Один lifecycle + skills; нет catalog 157 расширений | Opt-in глубина под размер работы (план A11) | Каталог и CLI Specify — ops-поверхность | Разъезд контрактов DF vs чужие команды | **не переносить** каталог. Профили lock **исследовать** (Q-001), не Specify CLI |
| SK-08 | A11-06: два аналога на S02/S04/S05 | Интеграции Copilot/Claude/Cursor/… + `generic --commands-dir` | SK-I1 | SUT A09: llama-server `:1240`, не IDE-agent | `generic` теоретически кладёт команды в каталог | Нужен свой харнесс; не first-class ornith | Несопоставимый прогон ≠ качество | **A11-06:** кандидат №2. Живой прогон **not-tested**. Обёртка CLI ≠ интеграция. Контракты достаточны |

### Лицензия (все строки SK-*)

MIT (GitHub, Inc.), [LICENSE v1.0.4](https://raw.githubusercontent.com/github/spec-kit/v1.0.4/LICENSE). Рекомендация «скопировать шаблон» в A12 обязана включить notice. Сейчас **не копировать**. Звёзды репозитория не взвешивают строки.

### Отказ от заимствования (намеренно)

Целиком Spec-Driven Development slash-workflow, constitution articles I–III как закон DF, converge без независимого oracle, замена Change YAML на `specs/<branch>/`.

---

## OpenSpec (A11-02)

Один механизм: **brownfield change-артефакты** (`openspec/changes/<id>/` = proposal + delta specs + design + tasks) и **слияние delta в основную spec при archive**. Не второй эксперимент: explore/verify/stores.

Pin: release **v1.12.0** (2026-09-03), commit `e062b9572be933564ba3899d059377dfa1393e32`. Источники: [experiments/A11-02/sources.md](../experiments/A11-02/sources.md). Лицензия: **MIT** (OpenSpec Contributors). Не копировать.

| ID | Проблема DF | Механизм OpenSpec | Evidence | Эквивалент DF | Выгода | Цена (контекст / ops) | Риск | Решение |
|---|---|---|---|---|---|---|---|---|
| OS-01 | Change FSM дорогой; A10-01 SDD не замена | `/opsx:propose` → `apply` → `archive`; expanded `verify` | OS-R1, OS-G2 | Intake→…→Verify/Archive ([A02-10](../experiments/A02-10/result.md)) | Меньше YAML; один folder на change | Нет `context_budget` слайса ([A03-05](../experiments/A03-05/result.md)); рекомендует Opus/Codex | «No rigid phase gates» = обход ANA-02/AB-06 | **не переносить** как замену ядра |
| OS-02 | F-010 / bootstrap: полный catalog до кода; S01 пустой spec | Delta-first: specs почти пустые, растут одним change; не документировать весь brownfield | OS-E1, OS-G1 | `spec-delta` + `docs/spec/**` + `_capabilities.yaml` (SPC-01/04) | Не варить океан spec | Main `openspec/specs/` неполный до многих archive | Агент пишет код без нормативного SSOT | **сохранить** spec-delta. Bootstrap «только затронутый slice» **исследовать** в A12 (F-010), не отключая гейт |
| OS-03 | SPEC-007: устаревшие требования; F-010 «specified» без live path | Archive: ADDED append, MODIFIED replace, REMOVED delete в `openspec/specs/`; optional `/opsx:sync` | OS-G1, OS-O1 | Specify пишет `docs/spec/**` **до** кода; `deltafuse archive` двигает пакет, не мержит spec | Явный merge modify/remove | SSOT обновляется **после** apply — spec не закон реализации | Код и главная spec расходятся до archive; ложный apply | **сохранить** Specify-time SSOT. Merge-только-на-archive **не переносить**. Пост-Verify сверка дельты ↔ live spec — [Q-008](../parking/design-questions.md) |
| OS-04 | Provenance архива (VER-05/06) | Папка в `openspec/changes/archive/<date>-<id>/` | OS-G1, OS-R1 | `docs/archive/changes/` + T8 no-overwrite, archive только после `converged` | Дата в имени | Нет доказательства `check_gate(converged)` в docs | Archive без Verify (F-009 класс) | **сохранить** DF archiver. Дату в пути **адаптировать** только если не ломает T8 |
| OS-05 | Human gate / FSM (AB-06) | «Enablers, not gates»: править proposal/design/tasks во время apply | OS-O1, OS-R2 | `blocked-on-decision`; allowed transitions | Итерация без стопа | Агент сам «согласовывает» | Скрытые DEC (SPEC-002) | **не переносить**. Fluid edits внутри фазы — не снятие гейта |
| OS-06 | SPC-05: Specify не читает `src/**` ([F-002](../../findings/F-002.md)) | `/opsx:explore` и v1.12.0 code-grounded propose читают код/тесты до артефактов | OS-E1, OS-A2 | Specify forbidden codebase; Analyze/Declare читают по контракту фазы | Предложение садится на реальный стек | Код в контексте Specify (A03-04 budget) | Spec = слепок кода, не закон | **сохранить** изоляцию Specify. Code-read в Explore/Analyze **исследовать** после routing, не в Specify |
| OS-07 | A11-06: тот же SUT | 30+ IDE/CLI; Cursor; `.agents`; нет llama-server | OS-T1, OS-R2 | SUT `:1240` ornith | Теоретически skills в `.agents` | Свой харнесс; модель не Opus | Несопоставимый прогон | **A11-06:** кандидат №1. Живой прогон **not-tested**. README Codex/Opus ≠ ornith. CLI не ставили |

### Лицензия (все строки OS-*)

MIT (OpenSpec Contributors), [LICENSE v1.12.0](https://raw.githubusercontent.com/Fission-AI/OpenSpec/v1.12.0/LICENSE). Копирование шаблонов — только с notice. Сейчас **не копировать**. Stars не взвешивают строки.

### Отказ от заимствования (намеренно)

Замена FSM на fluid propose/apply/archive; обновление нормативной spec только после кода; чтение `src/**` на Specify; markdown ADDED/MODIFIED вместо schema spec-delta.

---

## BMAD Method (A11-03)

Один механизм: **right-sized planning path** (глубина по размеру/ясности работы) плюс **именованные skills как роли** и **handoff контекста в `AGENTS.md`**. Не второй эксперимент: `bmad-loop`, Test Architect, web bundles.

Pin: release **v6.12.0** (2026-09-04), commit `05bfbd46d00766ec88eb9b42e76be2c575d64d7b`; docs https://docs.bmad-method.org/ 2026-09-08. Источники: [experiments/A11-03/sources.md](../experiments/A11-03/sources.md). Код **MIT**; знаки BMad **не** лицензированы. Не копировать skills и не использовать имя BMad в продукте DF.

| ID | Проблема DF | Механизм BMAD | Evidence | Эквивалент DF | Выгода | Цена (контекст / ops) | Риск | Решение |
|---|---|---|---|---|---|---|---|---|
| BM-01 | Q-001: один Analyze/lifecycle на все размеры; A10-01 tiny vs S05 | Choose a Planning Path + `bmad-build` выбирает ceremony **после** расследования (v6.12.0) | BM-R1, BM-D1, BM-D2, BM-A2 | Один FSM на Change; furrow не в lock | Tiny → меньше YAML; epic → spec+stories | `bmad-spec` потолок десятки тысяч токенов (A03-04 files-only budget) | Skip process / light path обходит Specify | **исследовать** профили lock (Q-001). Снятие гейтов для tiny **не переносить** |
| BM-02 | `docs/roles.md`: Analyst vs Implementer vs Maintainer | Skills `bmad-spec` / `bmad-architecture` / `bmad-ux` / `bmad-build` как «perspectives» | BM-R1, BM-D1 | Фазовые skills + Human Maintainer; запрет смешивать invent+code | Узкий skill на шаг | Несколько агентов/субагентов (BM-D2) — RAM/время ornith | Скрытый DEC, если «perspective» сам акцептует | **сохранить** фазы + Maintainer. Каталог персон **не переносить** |
| BM-03 | Повторно объяснять стек; Q-007 constitution | `bmad-project-context`: короткий verified блок в `AGENTS.md`, human approve | BM-D4 | `.deltafuse/lock.yaml`, `docs/spec/context.md`, шаблон AGENTS.md | Durable context без дерева репо в prompt | Сканирует package.json/CI — код в контексте | Блок раздувается (A03-04) | **исследовать** с Q-007. Не копировать BMAD markers |
| BM-04 | SPC-05 / F-002: Specify без `src/**` | `bmad-build` сначала читает codebase, потом light spec+code в одной сессии | BM-D2 | Specify forbidden src; Implement после specified | Меньше RTT на tiny | Spec = слепок кода | Закон после diff | **сохранить** изоляцию Specify. Investigate на Analyze/Declare — по контракту фазы |
| BM-05 | F-009 / A10-01: ложный Green своих тестов | `bmad-build` self-review + triage; optional skip review | BM-D2, BM-A2 | Hidden suite + Verify evidence (VER-*) | Дешевле человека на шуме | Review той же/соседней модели, нужны subagents | Самооценка ≠ oracle | **сохранить** независимый oracle. Self-review **не переносить** как Verify |
| BM-06 | AB-06 Human Gate | `bmad-build-auto` без ожидания человека; Loop orchestrates units | BM-D1, BM-D2 | `blocked-on-decision`; запрет auto-accept | Скорость после стабильных паттернов | Обход DEC/spec | SPEC-002 | **не переносить** unattended как default |
| BM-07 | A11-06: тот же SUT | Installer: Claude Code, Cursor; v6.12.0 + Grok/ZCode/Polytoken; нет llama-server | BM-D5, BM-D6, BM-A2 | SUT `:1240` ornith | Skills в IDE | Node/Python/uv; не first-class ornith | Несопоставимый прогон | **A11-06:** не в паре (нет generic-хука). Живой прогон **not-tested**. `--list-tools` не запускали |

### Лицензия (все строки BM-*)

MIT на **код** (BMad Code, LLC), [LICENSE v6.12.0](https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/v6.12.0/LICENSE). Товарные знаки — [TRADEMARK.md](https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/v6.12.0/TRADEMARK.md): не называть продукт/модуль DF «BMad*». Копирование skills — только с MIT notice **и** без чужого бренда. Сейчас **не копировать**. Stars не взвешивают строки.

### Отказ от заимствования (намеренно)

Пропуск Specify для «trivial»; light path spec+code в одном чате; `bmad-build-auto` / Loop как замена FSM; self-review вместо hidden suite; брендинг BMad.

---

## Kiro Specs (A11-04)

Один механизм: связка **requirements → design → tasks** и качество **проверяемых требований** (EARS, Analyze Requirements, optional PBT). Не второй эксперимент: steering, vibe mode, MCP import.

Pin: публичные docs https://kiro.dev/docs/specs/ (updated 2026-08-27); git/release **нет**. Источники: [experiments/A11-04/sources.md](../experiments/A11-04/sources.md). Продукт proprietary — **не копировать** `.kiro/` шаблоны. EARS и PBT как методы — не эксклюзив Kiro.

| ID | Проблема DF | Механизм Kiro | Evidence | Эквивалент DF | Выгода | Цена (контекст / ops) | Риск | Решение |
|---|---|---|---|---|---|---|---|---|
| KI-01 | Три слоя intent (spec / design / tasks) легко разъезжаются; F-010 specified без live spec | Три файла в `.kiro/specs/<feature>/`: requirements, design, tasks | KI-S1 | `docs/spec/**` + `DEC-*` + `TASK-*` (SPC-01, DEC-02/03) | Явная тройка артефактов | Три markdown без schema; `#spec` кладёт все в чат (A03-04) | SSOT в `.kiro` vs `docs/spec` | **сохранить** DF пакет. Три файла Kiro **не переносить** |
| KI-02 | SPEC-003/004: расплывчатый язык, слабый oracle | EARS: WHEN condition THE SYSTEM SHALL behavior | KI-S2 | RFC 2119 MUST/SHALL в spec; TASK oracle GIVEN/WHEN/THEN | Короткая проверяемая форма | Стиль не гейт | SHALL без входа/выхода (F-010 класс) | **исследовать** EARS как стиль `docs/spec/**` (SPEC-003), не новый формат файлов |
| KI-03 | SPEC-002 / Analyze gaps | Analyze Requirements: cross-set inconsistencies, ambiguities, edges | KI-S3 | `routing.yaml` Ambiguous + DEC proposed (ANA-02) | Ловит противоречия между req | Минуты LLM; можно skip | Self-review, не `check_gate` | **сохранить** DEC gate. Analyze как prompt extra **исследовать**; не замена F-010 |
| KI-04 | Design vs spec (SPC-05) | Design-First: design.md затем требования из архитектуры | KI-S2 | Spec закон до кода; DEC после вилки | Удобно для NFR/feasibility | Spec = слепок дизайна | Обход «spec primary» (`docs/roles.md`) | **не переносить** как Specify. Design-First только как вход в DEC, не в `docs/spec` |
| KI-05 | AB-06 Human Gate | Quick Spec: три артефакта без approval между фазами | KI-S4, KI-S5 | specification-proposed → specified | Скорость на знакомом | Нет стопа человека | Скрытые допущения | **не переносить** |
| KI-06 | S03 баги / F-009 / regression | Bugfix: current / expected / **unchanged**; PBT на три свойства | KI-S6 | Red evidence + regression evidence (TAR/IMP) | Явный «не ломай» | PBT только IDE; optional | Слабое property = ложный pass (docs сами) | **сохранить** Red+regression. Unchanged-behavior в spec-delta **исследовать**. Генератор Kiro PBT **не переносить** |
| KI-07 | TEST-001: example-only тесты | PBT из EARS; shrinking; не formal verification | KI-S7 | Hidden/pytest examples; TASK oracle | Много входов из одного инварианта | IDE-only; слабые properties | Подмена hidden suite | **исследовать** Hypothesis-класс в A12 как optional Declare. Не ранжировать vs ornith |
| KI-08 | DEC-01 DAG; ornith serial | Parallel waves по зависимостям tasks.md | KI-S1 | topo-sort; фазы по одной задаче | Скорость на облаке | 8 GB / одна модель | Гонки, раздутый контекст | **не переносить** на SUT A09 |
| KI-09 | A11-06 тот же SUT | Kiro IDE/CLI/Web; PBT только IDE; модель продукта | KI-S1, KI-S7 | `:1240` ornith | — | Vendor lock | Несопоставимо | **A11-06:** **not-applicable**. Не кандидат пары. Контракты достаточны |

### Лицензия (все строки KI-*)

Kiro — закрытый продукт AWS; SPDX не опубликован. Docs copyright. **Не копировать** шаблоны и длинные фрагменты. EARS (публичная нотация) и PBT как идея тестирования лицензией Kiro не запрещены как *методы*, но реализация Kiro — да.

### Отказ от заимствования (намеренно)

`.kiro/specs/` как SSOT; Quick Spec; Design-First Specify; parallel task execution на локальном SUT; закрытый PBT-генератор.

---

## Primary practices (A11-05)

Не пятый фреймворк. Привязка: находки A02–A07 + протокол A07-03. Источники: [experiments/A11-05/sources.md](../experiments/A11-05/sources.md). Аналоги A11-01…04 не переранжировать. F-006…F-010 вне скоупа этой секции.

| ID | Проблема DF | Практика | Evidence | Эквивалент DF | Выгода | Цена (контекст / ops) | Риск | Решение |
|---|---|---|---|---|---|---|---|---|
| PP-01 | DEC уже есть; путать ADR-superseded с task-cancelled | Nygard ADR: status proposed/accepted/deprecated/**superseded** | PP-S1 | `DEC-*` + human gate (AB-06, DEC-02/03) | Явный audit trail решений | Ещё один шаблон поверх schema | Авто-accept DEC | **сохранить** `DEC-*`. Шаблоны блога **не нужны**. Отказ: если практика снимает human gate или подменяет `decision.schema.yaml` |
| PP-02 | Oracle задачи без наблюдаемого поведения | North BDD: Given / When / Then | PP-S2 | TASK oracle уже GWT | Общий язык приёмки | Cucumber/JBehave слой | Подмена hidden suite / Red evidence | **сохранить** GWT в TASK. Cucumber **не переносить**. Отказ: если Gherkin заменяет pytest Red или Verify |
| PP-03 | SPEC-003 расплывчатый язык | RFC 2119 MUST/SHALL | PP-S3 | SPEC-003 в `docs/spec/**` / spec-delta | Нормативные глаголы уже критерий | Нет | Ослабить до SHOULD-everywhere | **сохранить** RFC 2119. Отказ: замена нормативности «EARS-only» без MUST/SHALL |
| PP-04 | SPEC-003/004: слабая форма входа/выхода | EARS WHEN … THE SYSTEM SHALL (IEEE RE 2009) | PP-S4; KI-02 | RFC 2119 + TASK GWT | Короткая проверяемая форма | Стиль, не гейт; PDF paywalled | SHALL без live spec (F-010) | **исследовать** EARS как *стиль* `docs/spec/**`. Файлы `.kiro` **не переносить**. Отказ: новый формат файлов или ослабление F-010 |
| PP-05 | Vacuous product tests (A07-03 FDR) | Mutation testing (PIT mutators / A07-03 M1–M4) | PP-S5; A07-03 | Hidden suite + FDR protocol | Ловит фиктивный Green | PIT = JVM bytecode; ops | Мутировать *тесты* под Green; mutation как Specify gate | **сохранить** протокол A07-03 как oracle. PIT **не** вендорить в ядро. Отказ: mutation score вместо spec / Red evidence |
| PP-06 | TEST-001 example-only | Property-based testing (Hypothesis / QuickCheck) | PP-S6; KI-07 | Hidden/pytest examples; TASK oracle | Много входов из инварианта | Нет локального раннера на `:1240` | Подмена hidden suite; слабые properties | **исследовать** optional Declare (KI-07). Генератор Kiro **не переносить**. Отказ: PBT вместо example hidden suite без локального runner |
| PP-07 | F-001 CRLF / lock hash | Reproducible artifacts + `gitattributes` `eol=lf` | PP-S7, PP-S8; F-001 | нет `.gitattributes`; `framework_hash` считает байты | LF в индексе → стабильный SHA lock | Один файл атрибутов | Заявить DF как reproducible *binary* build | **адаптировать** `.gitattributes` / LF для lock hash (уже фикс F-001). Отказ: SOURCE_DATE_EPOCH / bit-identical markdown как цель фреймворка |
| PP-08 | F-005 `cancelled`/`superseded` не терминальны на `converged` | NIST SP 800-128: авторизованное изменение, baseline, audit; Nygard superseded как *класс* статуса | PP-S9, PP-S1; F-005 | schema task enum vs `fsm.py` `converged` | Можно закрыть пакет после отмены/замены задачи | Правка FSM + тесты T-гейт | ITIL/CMDB церемония; снятие Verify | **адаптировать** `converged`: `cancelled`/`superseded` терминальны. Отказ: ITIL-процесс или drop Verify |
| PP-09 | F-004 path traversal / silent skip | OWASP Path Traversal: каноникализация, путь внутри корня | PP-S10; F-004 | `validate_spec_ref` без `is_relative_to` | Закрывает выход за repo root | Несколько строк + тесты | «полный AppSec» как ядро DF | **адаптировать** `is_relative_to` / отказ на `../`. Один доп. источник плана («пробел»). Отказ: отдельная AppSec-программа вместо точечного фикса |
| PP-10 | Нет finding про consumer/provider API между сервисами | Pact consumer-driven contracts | PP-S11 | TEST-002 публичный интерфейс модуля | — | Broker, версии контрактов | Overkill для фреймворка без service mesh | **не переносить**. Отказ от внедрения: нет A02–A07 дефекта, который Pact закрывает лучше TEST-002 |

### Исключено из именованного набора (причина)

| ID | Находка | Почему ADR/BDD/EARS/RFC/PBT/mutation/repro/CM/Pact не ответ |
|---|---|---|
| PP-X1 | F-002: `PHASE_CONTRACTS` мёртв; у TASK нет `context_budget` | Ни одна из практик не sandbox'ит FS и не валидирует бюджет фазы. Это enforcement контракта чтения (CODE-002 / PROC-004), не ADR и не mutation. Чинить кодом FSM, не практикой из списка |
| PP-X2 | F-003: `words * 1.3` | Tokenizer SUT (Q-002). BDD/PBT/NIST не считают BPE |

### Лицензия (строки PP-*)

См. [sources.md](../experiments/A11-05/sources.md). Копировать IEEE PDF, эссе North, шаблоны Pact/Cucumber, раннер PIT **нельзя**. Методы (GWT, MUST/SHALL, mutators как *идея*, EOL в git) — да, с условием отказа в строке.

### Отказ от заимствования (намеренно)

Cucumber/JBehave; вендор PIT в `src/deltafuse`; Pact broker; Kiro PBT generator; `.kiro` файлы; ITIL/CMDB; reproducible-builds как обещание бинарной сборки DF; constitution/slash-SDD заново (уже A11-01…04).

---

## A11-06 — два аналога на S02 / S04 / S05

Не живой ранг. Источники: [experiments/A11-06/sources.md](../experiments/A11-06/sources.md). Пара: **OpenSpec** (кандидат №1) и **Spec Kit** (кандидат №2). BMAD не в паре. Kiro **not-applicable**. Решения A11-01…05 не переписывать. Качество **не** ранжировать.

Сопоставимость (план A11 + protocol §1/§4): та же модель `ornith-1.5-35b-a3b` на `:1240`, те же raw input/oracles/бюджеты, один case за запуск, S05 = holdout (не тюнить промпт). First-class интеграция аналогов с llama-server **отсутствует** (SK-I1, OS-T1). SUT 2026-09-08 **reachable**. Установка CLI и обёртка slash-команд была бы новым харнессом (класс A10-01), не продуктом аналога.

| ID | Case | Измерено DF | Контракт Spec Kit | Контракт OpenSpec | Живой ранг |
|---|---|---|---|---|---|
| CMP-01 | S02 tiny (calibration) | A09 `partial`: TASK Green, 0 Verify, F-009 | specify→plan→tasks→implement; нет typed TASK (SK-03) | change folder propose/apply; нет гейта (OS-01) | **not-tested** |
| CMP-02 | S04 Decision (calibration) | A09 `pass`: `blocked-on-decision` + DEC | clarify рекомендован, не FSM-блок (SK-05) | «no rigid phase gates» (OS-05) | **not-tested** |
| CMP-03 | S05 multi-cap (holdout) | A09 `fail` Specify/F-010; A10-01 SDD файлы ≠ hidden-green | converge = self-review (SK-04); holdout нельзя калибровать | несколько delta spec, merge на archive (OS-03) | **not-tested** |

### Решение

Контракты достаточны для A12: **не** объявлять analog лучше/хуже DF на этих case. Заимствования только из строк SK/OS/BM/KI/PP с уже записанным условием отказа. Повторный живой ранг — только при first-class адаптере того же `:1240`.

### Отказ от заимствования (намеренно)

Ранг качества Copilot/Claude/Opus/Kiro vs ornith; установка analog CLI «чтобы закрыть карточку»; повтор homemade SDD A10-01 как будто это Spec Kit/OpenSpec.


