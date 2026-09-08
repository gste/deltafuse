# Сравнение аналогов с DeltaFuse (A11)

Дата старта: 2026-09-08. Карточки A11-02+ **дописывают** секции, не переписывая решения A11-01 без новой evidence.

Формат плана A11: проблема → механизм аналога → первичное evidence → эквивалент DF → выгода → цена → риск → решение. Решения: **сохранить своё** / **адаптировать** / **исследовать** / **не переносить** / **упростить/удалить своё**. Популярность ≠ proof. Копирование ресурсов — только после лицензии.

Пакетный путь `analysis/matrices/contracts.md` нет; строки DF — [backlog/matrices/contracts.md](../matrices/contracts.md) (ANA-01/02, SPC-01/06).

Живой LLM-ранг vs ornith: **not-tested** до A11-06. A10-01 уже показал, что минимальный SDD не замена ядра.

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
| SK-08 | A11-06: два аналога на S02/S04/S05 | Интеграции Copilot/Claude/Cursor/… + `generic --commands-dir` | SK-I1 | SUT A09: llama-server `:1240`, не IDE-agent | `generic` теоретически кладёт команды в каталог | Нужен свой харнесс; не first-class ornith | Несопоставимый прогон ≠ качество | Для A11-06: Spec Kit **not-tested** на ornith, пока нет того же SUT. Контракты достаточны. `generic` не проверяли установкой |

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
| OS-06 | SPC-05: Specify не читает `src/**` ([F-002](../../findings/F-002.md)) | `/opsx:explore` и v1.12.0 code-grounded propose читают код/тесты до артефактов | OS-E1, OS-A2 | Specify forbidden codebase; Analyze/Target читают по контракту фазы | Предложение садится на реальный стек | Код в контексте Specify (A03-04 budget) | Spec = слепок кода, не закон | **сохранить** изоляцию Specify. Code-read в Explore/Analyze **исследовать** после routing, не в Specify |
| OS-07 | A11-06: тот же SUT | 30+ IDE/CLI; Cursor; `.agents`; нет llama-server | OS-T1, OS-R2 | SUT `:1240` ornith | Теоретически skills в `.agents` | Свой харнесс; модель не Opus | Несопоставимый прогон | Для A11-06: OpenSpec **not-tested** на ornith. Контракты достаточны. CLI не ставили |

### Лицензия (все строки OS-*)

MIT (OpenSpec Contributors), [LICENSE v1.12.0](https://raw.githubusercontent.com/Fission-AI/OpenSpec/v1.12.0/LICENSE). Копирование шаблонов — только с notice. Сейчас **не копировать**. Stars не взвешивают строки.

### Отказ от заимствования (намеренно)

Замена FSM на fluid propose/apply/archive; обновление нормативной spec только после кода; чтение `src/**` на Specify; markdown ADDED/MODIFIED вместо schema spec-delta.
