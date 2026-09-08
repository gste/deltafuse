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
