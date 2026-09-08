# Отложенные вопросы доработки DeltaFuse

Живой список идей, которые **не исполнять** в A09–A11. Разбор — карточка [A12-04](../packets/A12-04.md), затем включение в roadmap [A12-03](../packets/A12-03.md).

Как добавить: новый `Q-NNN` в конец, дата, источник (карточка/finding/чат), вопрос, черновик направления, что **не** делать. Не патчить skills/`integrity.py` отсюда.

Статус записей: `parked` → после A12-04 `accept` / `defer` / `reject`.

## Q-001 — Ширина борозды как профиль, не хардкод skill

- **Дата:** 2026-09-06
- **Источник:** A09-01a/b калибровка ornith; обсуждение 14B vs 27B+
- **Критерии:** `PROC-004`, `PROC-007`
- **Статус:** `parked`

**Вопрос.** Должен ли DeltaFuse явно регулировать, сколько артефактов пишет один LLM-вызов (узкая / средняя / широкая борозда), отдельно от бюджета чтения `context.max_tokens` / `max_files`?

**Наблюдение.** В docs борозда заявлена (`context_budget` слайса, 16000/24). В runtime не крутится: skill Analyze всё равно требует `routing.yaml` + slices + `coverage.yaml` + `analysis.md` одним ходом. У задачи нет `context_budget` ([F-002](../../findings/F-002.md)). Спас A09 харнесс `A09_ANALYZE_FOCUS=routing|slices|coverage`, не контракт фреймворка. Для ornith/14B узкая борозда нужна; для 27B+ три RTT слегка избыточны, не вредны.

**Черновик направления.** Профиль ширины *вызова* в конфиге продукта/lock (`narrow` / `medium` / `wide`): один артефакт; фаза целиком; фронтир пакует Analyze сам. FSM уже пофазовый; нужны **подшаги внутри фазы** и правило «не закрывай `analyzed`, пока нет routing+slices+coverage», без требования одного ответа. Не копировать skills под каждую модель.

**Не делать до A12-04.** Не вшивать ornith-сплит как единственный режим Analyze.

## Q-002 — Счётчик токенов = tokenizer SUT + калибровка endpoint

- **Дата:** 2026-09-06
- **Источник:** [F-003](../../findings/F-003.md), [A03-01](../packets/A03-01.md); обсуждение калибровки под LLM пользователя
- **Критерии:** `PROC-004`, `PROC-007`
- **Статус:** `parked`

**Вопрос.** Чем заменить `words * 1.3` так, чтобы бюджет контекста совпадал с токенами той модели, которой пользуется продукт?

**Наблюдение.** A03-01 уже сравнил эвристику с `/tokenize` Qwen/Ornith: RU −38%, код −52%, YAML −70%. Объективный счётчик есть у runtime; `estimate_tokens` им не пользуется. Эвристика даёт ложный pass при 16k.

**Черновик направления.**

1. Adapter к tokenizer пользователя: `POST /tokenize` (llama-server / Studio) или офлайн vocab GGUF/`tokenizers`.
2. Разовая калибровка при пине модели (`deltafuse calibrate` или шаг lock): фикстуры skill+schema+слайс → профиль: vocab/id, overhead ChatML, размер skill, резерв ответа, запас reasoning.
3. Фолбэк без эндпоинта: коэффициенты по типу файла из F-003 (`.yaml`×4, код×2.7, кириллица×2.2), консервативно.
4. Лестница prefilla (ширина борозды / TTFT) калибруется отдельно от счётчика (см. Q-001, очередь W01).

**Не делать.** Не считать токены генерацией LLM. Не подменять tokenizer эмбеддингами (Q-003).

## Q-003 — Эмбеддинги для отбора файлов, не для длины

- **Дата:** 2026-09-06
- **Источник:** обсуждение F-003
- **Критерии:** `PROC-004`
- **Статус:** `parked`

**Вопрос.** Нужен ли локальный embedding-ранжировщик, чтобы решать *какой* файл класть в борозду?

**Черновик.** Это retrieval, не budget. Имеет смысл только если A12 режет контекст по релевантности claim→file. Не чинит F-003.

**Не делать.** Не подключать эмбеддинг «чтобы точнее считать токены».

## Q-004 — Вложенный вызов SUT «посчитай токены» — отказ

- **Дата:** 2026-09-06
- **Источник:** обсуждение калибрирующего промпта Ornith→Ornith
- **Критерии:** `PROC-007`
- **Статус:** `parked` (кандидат на `reject` в A12-04)

**Вопрос.** Стоит ли калибровать бюджет промптом «сколько здесь токенов» или вложенным chat-completions?

**Черновик отказа.** Модель угадывает число, не считает BPE. Prefill дороже `/tokenize`; `usage.prompt_tokens` после chat всё равно платит генерацией. Вложенный SUT смешивает харнесс и испытуемого.

Зафиксировать в A12-04 как явный `reject`, чтобы не возвращаться.

## Q-005 — Docs-only без обязательного Red/Green по коду

- **Дата:** 2026-09-07
- **Источник:** [A09-07](../packets/A09-07.md) holdout S08b
- **Критерии:** `PROC-003`, `SPEC-006`, `CODE-002`
- **Статус:** `parked`

**Вопрос.** Должен ли lifecycle пропускать Target/Implement (или требовать только docs-артефакты), когда `code_change_expected: false` / docs-only, вместо обязательного Red pytest и Green по `src/`?

**Наблюдение.** S08b Specify на 3/3 записал примеры, RFC 2697, Leaky Bucket и правку опечатки. Frozen harness на Implement всё равно требует `src/ratelimit/limiter.py`. r2: TASK-001 `allowed_paths` только spec, Target `already-green`, затем модель сначала снова писала docs, потом сломала `is_blocked`. Схема `routing.yaml` не имеет поля `type: docs`.

**Черновик направления.** Маршрут docs/no-code: закрывать Change на Specify/Decompose/Verify трассировки без Red/Green кода; либо Target пишет не-pytest evidence. Не смешивать с багом (S03) и фичей (S02).

**Не делать до A12-04.** Не ослаблять Implement в A09 holdout и не добавлять S08 extras в frozen prompts.

## Q-006 — Operational files вне Specify/Implement

- **Дата:** 2026-09-07
- **Источник:** [A09-08](../packets/A09-08.md) holdout S08c
- **Критерии:** `PROC-003`, `SPEC-006`, `CODE-002`
- **Статус:** `parked`

**Вопрос.** Где в lifecycle писать `deploy/`, `monitoring/`, `docs/ops/` при `spec_change_expected: false` и `code_change_expected: false`, если Specify закрывает только `spec-delta`/`docs/spec/**`, а frozen Implement требует `src/ratelimit/limiter.py`?

**Наблюдение.** S08c 0/3 не обновили hostname/port/log/health/runbook. r3 Specify FSM pass с `requirement_delta: none` ([F-010](../../findings/F-010.md)), Decompose на schema `TASK-NNN`. Spec и код не тронуты. Routing без `type: operational`.

**Черновик направления.** Маршрут ops: артефакты вне spec/src как allowed_paths задачи без Red/Green кода; или отдельный skill/verify для ops-файлов. Связано с Q-005.

**Не делать до A12-04.** Не учить Specify писать deploy YAML в A09.

## Q-007 — Constitution как профиль lock, не девять статей Spec Kit

- **Дата:** 2026-09-08
- **Источник:** [A11-01](../packets/A11-01.md) Spec Kit v1.0.4 (`/speckit.constitution`, `memory/constitution.md`)
- **Критерии:** `PROC-001`, `SPEC-002`
- **Статус:** `parked`

**Вопрос.** Нужен ли DeltaFuse отдельный машиночитаемый набор non-negotiables проекта (как constitution), отдельно от `docs/spec/context.md` и skills, чтобы plan/specify сверялись с профилем lock?

**Наблюдение.** Spec Kit задаёт principles один раз на проект и гоняет их через plan/analyze. Статьи I–III методологии (library-first, CLI-everywhere, TDD before code) не совпадают с Change FSM. A03-04: бюджет DF считает файлы, не полный prompt — длинная constitution в каждом вызове дорогая. Human gate DF уже есть (AB-06); constitution не заменяет `DEC-*`.

**Черновик направления.** Короткий lock-профиль принципов (ширина борозды Q-001 + запреты вроде «не auto-accept DEC») без копирования nine articles. Сверка — FSM/schema, не LLM-чеклист.

**Не делать до A12-04.** Не копировать Spec Kit templates/constitution. Не патчить skills.

## Q-008 — Сверка spec-delta с live spec после Verify, не перенос SSOT на archive

- **Дата:** 2026-09-08
- **Источник:** [A11-02](../packets/A11-02.md) OpenSpec v1.12.0 (`/opsx:archive` merge ADDED/MODIFIED/REMOVED)
- **Критерии:** `SPEC-007`, `SPEC-001`
- **Статус:** `parked`

**Вопрос.** Нужна ли после Verify (до `deltafuse archive`) независимая сверка, что операции spec-delta попали в существующие файлы `docs/spec/**`, отдельно от гейта `specified`?

**Наблюдение.** OpenSpec держит истину в change-delta и вливает её в `openspec/specs/` только на archive — после `/opsx:apply`. DeltaFuse пишет нормативную spec на Specify (закон до кода). F-010: `specified` зелёный без live paths. SPEC-007 требует явных modify/remove, не «только дописать».

**Черновик направления.** Усилить `specified` (live paths, F-010) **и** опциональный check на `converged`: ADDED/MODIFIED/REMOVED из spec-delta согласованы с диском. Не переносить OpenSpec «главная spec обновляется после кода».

**Не делать до A12-04.** Не двигать SSOT на archive. Не патчить skills в A09–A11.

## Уже закрыто findings, не дублировать здесь

Исправления контракта после доказательств: [F-002](../../findings/F-002.md) PHASE_CONTRACTS, [F-003](../../findings/F-003.md) эвристика, [F-008](../../findings/F-008.md) extractor `CR-*`, [F-009](../../findings/F-009.md) фальшивый Red. Их приоритет — A12-03 по типу finding, не этот список.
