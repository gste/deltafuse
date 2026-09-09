# Roadmap проверяемых изменений DeltaFuse (A12-03)

Дата: 2026-09-08. Карточка [A12-03](packets/A12-03.md). Входы: [summary.md](summary.md), [A12-04](experiments/A12-04/result.md), [parking](parking/design-questions.md), приоритеты [плана A12](../analysis-plan.md).

**Это не внедрение.** Принятие и реализация каждого `RM-*` — отдельный продуктный Change после этой очереди аудита. Skills / `integrity.py` / `fsm.py` **не** патчить этой карточкой.

P0 не усреднять с P3. Не заменять ядро на analog SDD. Q-003/Q-004/Q-007 **не** строки roadmap (defer/reject).

Владелец реализации: Maintainer. SUT проверки после фикса: тот же `:1240` ornith **или** контрактные тесты ядра — как указано в пункте.

Ядро, которое roadmap **не** упрощает: FSM-гейты, Specify-time `docs/spec/**`, typed TASK, Human DEC, независимый hidden/pytest, T8 archive, RFC 2119, GWT.

---

## Порядок внутри приоритета

Не «средний score». Сначала независимый P0-security, затем стоп holdout, затем ложный TDD, затем stale evidence. P1 дешёвый F-001 можно параллелить с любым P0.

```text
RM-004 → RM-010 → RM-009 → RM-006
         RM-001 (параллельно, P1)
         RM-008 после RM-010
RM-002 / RM-003 / RM-005 / RM-008  (P1)
RM-020 / RM-021 / RM-022           (P2)
RM-030 / RM-031                    (P3)
```

---

## P0 — ложное соответствие, повреждение, обход gate

### RM-004 — каноникализация путей (F-004)

| | |
|---|---|
| Эффект | Нет чтения/валидации файлов вне `repo_root`; нет тихого skip несуществующих путей в оценке токенов |
| Минимум | `Path.is_relative_to(repo_root)` (или эквивалент) после `resolve()` в `validate_spec_ref` / оценка файлов; ошибка, не `None` |
| Слои | `integrity.py`, `context.py`; тесты fuzz `../` |
| Критерии | `CODE-006`, `PROC-004` |
| Acceptance | Репро F-004: `../outside_spec.md` → ошибка гейта; существующий валидный spec_ref → pass |
| Regression | T1–T8 и layout-тесты зелёные; легитимные относительные пути внутри repo |
| Стоимость | S (часы) |
| Зависимости | нет |
| Не делать | AppSec-программа; ослабить F-010 |
| Статус | **done** 2026-09-08 — `path_is_inside_repo` после `resolve()` в `validate_spec_ref` / `validate_decision_ref` / `validate_context_budget`; missing paths — ошибка; токены дедуплицируются |

### RM-010 — гейт `specified` требует live spec (F-010)

| | |
|---|---|
| Эффект | Vacuous `gate ok` без `docs/spec/**` / catalog не проходит; holdout Specify перестаёт быть ложным pass |
| Минимум | Для каждой операции add/modify в spec-delta: файл (и якоря) существуют под `docs/spec/**`. Bootstrap: живой файл capability + согласованный `_capabilities.yaml`. `requirement_delta: none` только с точными `spec_refs` на **существующие** якоря (S03) |
| Слои | `fsm.py` `specified`; схемы spec-delta/catalog; **не** чеклист LLM и не патч skill вместо гейта |
| Критерии | `SPEC-001`, `SPEC-006`, `SPEC-004` |
| Acceptance | Фикстура S01/S05: нет `ratelimit.md` / `usage_stats.md` → `specified` fail. Пакет с записанными live файлами → pass. S03 unchanged spec + none + live refs → pass |
| Regression | AB-06 S04: нет Specify. Не требовать код на `specified`. Не отключать гейт (AB-01) |
| Стоимость | M |
| Зависимости | RM-004 желателен (те же пути) |
| Не делать | OpenSpec merge на archive; Spec Kit checklist как замена |
| Статус | **done** 2026-09-08 — гейт `specified` требует status, валидный catalog, live `docs/spec/**` для add/modify и якоря `spec_refs` для none; skills не патчились |

### RM-009 — аутентичный Red / already-green (F-009)

| | |
|---|---|
| Эффект | Target не закрывает overshoot фиктивным Red и не смотрит в `_private` |
| Минимум | (1) `already-green`, если публичный оракул уже выполняется; (2) отказ Red-теста с импортом приватных символов; (3) не выдумывать падение, если поведение уже в diff TASK-001 |
| Слои | FSM `targeting` + схема evidence; при необходимости инструкция Target — **после** гейта, не вместо |
| Критерии | `TEST-004`, `TEST-002` |
| Acceptance | Репро S02 TASK-002: уже реализованный lift → `already-green` или halt, не `expected-failure` на private. Hidden suite A10-01 класс: свои тесты pass + hidden fail остаётся fail продукта |
| Regression | S03 authentic Red на отсутствующий `int()` / поведение. Hidden suite не заменяется |
| Стоимость | M |
| Зависимости | нет (можно параллельно RM-010) |
| Не делать | mutation score как Specify; ослабить hidden |
| Статус | **done** 2026-09-08 — `already-green` в evidence; Red с `._` / `_private` отвергается; target-task уточнён после гейта |

Тип F-009 — дефект TDD/агента, не только FSM: минимум всё равно **проверяемый гейт**, не «напишите лучше промпт».

### RM-006 — инвалидация stale evidence (F-006)

| | |
|---|---|
| Эффект | Green/regression не silent-pass после смены spec/кода baseline |
| Минимум | Evidence несёт `base_revision` (или hash spec+src, на которые ссылается задача); `implemented`/`converged` fail, если ревизия не совпадает с деревом |
| Слои | `evidence.schema.yaml`, `fsm.py` |
| Критерии | `SPEC-007`, `TEST-005`, `PROC-002` |
| Acceptance | Репро A05-04: после подмены spec при старом green yaml → гейт fail. Свежий прогон на текущем дереве → pass |
| Regression | Честный Green на неизменном baseline. SUT F-006 по-прежнему **not-tested** до серии Changes — закрывать контрактным тестом, не ждать S11 |
| Стоимость | M |
| Зависимости | нет |
| Не делать | доверять timestamp агента без содержимого |
| Статус | **done** 2026-09-09 — `base_revision` = hash `docs/spec/**`+`src/**`; stale Green ломает `implemented`/`converged` |

---

## P1 — bounded execution, восстановление, межсрез/claims

### RM-001 — `.gitattributes` / LF (F-001)

| | |
|---|---|
| Эффект | bash smoke на Windows; стабильный `framework_hash` |
| Минимум | `.gitattributes`: `* text=auto` + `*.sh text eol=lf` (и lock/yaml по необходимости) |
| Слои | корень репо; не SOURCE_DATE_EPOCH |
| Критерии | `BASE-005`, PROC lock |
| Acceptance | Репро F-001: `bash tests/smoke-test.sh` в WSL после checkout; hash LF==Linux |
| Regression | PS smoke; бинарные файлы не портятся |
| Стоимость | S; **можно сразу**, параллельно P0 |
| Зависимости | нет |
| Статус | **done** 2026-09-08 — корневой `.gitattributes` (`* text=auto eol=lf`, `*.sh text eol=lf`, `*.ps1 text eol=crlf`) |

### RM-002 — enforcement `PHASE_CONTRACTS` и task budget (F-002)

| | |
|---|---|
| Эффект | Чтение/запись вне контракта фазы и переполнение task-бюджета ломают гейт, не docs |
| Минимум | Использовать `PHASE_CONTRACTS` в `fsm.py`; `context_budget` на TASK; `validate_context_budget` на Target/Implement |
| Слои | `fsm.py`, `task.schema.yaml`, `context.py` |
| Критерии | `PROC-004`, `CODE-002` |
| Acceptance | Репро F-002: TASK без budget / 50 файлов → decomposed/targeting fail. Легитимный слайс 16k/24 → pass |
| Regression | Analyze по-прежнему требует routing+slices+coverage. Не sandbox через ADR/Pact |
| Стоимость | M–L |
| Зависимости | RM-003 желателен для честных токенов; иначе conservative fallback |
| Статус | **done** 2026-09-09 — TASK `context_budget` обязателен; budget на spec_refs+allowed_paths; Red/Green `changed_paths` сверяются с `PHASE_CONTRACTS`; tokenizer пока `words * 1.3` |

### RM-003 — tokenizer вместо `words * 1.3` (F-003, Q-002)

| | |
|---|---|
| Эффект | lint-context не даёт ложный pass на YAML/RU/код |
| Минимум | Upper bound: коэффициенты A03-01 (yaml×4, код×2.7, RU×2.2) **или** `POST /tokenize` если endpoint есть. Фолбэк без LLM-счёта |
| Слои | `context.py`, CLI; optional lock pin |
| Критерии | `PROC-004`, `PROC-007` |
| Acceptance | Фикстуры A03-01: оценка ≥ реальных токенов. YAML не занижен на 70% |
| Regression | EN текст не раздувается абсурдно. **reject Q-004** (не chat «сколько токенов») |
| Стоимость | M |
| Зависимости | нет |
| Не делать | эмбеддинги (Q-003 defer) |
| Статус | **done** 2026-09-09 — upper bound A03-01 (yaml×4.5, code×2.7, RU×2.2, log×4.8); optional `DELTAFUSE_TOKENIZE_URL`; без chat completions |

### RM-005 — терминалы `cancelled`/`superseded` на `converged` (F-005)

| | |
|---|---|
| Эффект | Переразбор задач не клинит пакет; не нужно фальшивое `implemented` |
| Минимум | `converged`: status ∈ {implemented, verified, cancelled, superseded} |
| Слои | `fsm.py`; тест T3 расширить |
| Критерии | `PROC-002`, `PROC-003` |
| Acceptance | Репро F-005: TASK cancelled + остальные verified → converged pass. pending → fail |
| Regression | Не drop Verify. Не ITIL |
| Стоимость | S |
| Зависимости | нет |
| Статус | **done** 2026-09-09 — `converged` принимает `cancelled`/`superseded`; `pending` по-прежнему fail; Verify не снят |

### RM-008 — сверка spec-delta ↔ диск на `converged` (Q-008)

| | |
|---|---|
| Эффект | После кода spec на диске всё ещё соответствует delta (defense in depth к RM-010) |
| Минимум | На `converged`: операции ADDED/MODIFIED/REMOVED отражены в `docs/spec/**` (файлы/якоря). Не LLM-review. **Не** merge SSOT на archive |
| Слои | `fsm.py` |
| Критерии | `SPEC-007`, `SPEC-001` |
| Acceptance | Пакет, стёрший live spec после Specify → converged fail. Честный пакет после RM-010 → pass |
| Regression | T8 archive. Specify-time SSOT сохраняется |
| Стоимость | S–M |
| Зависимости | **RM-010** |
| Статус | **done** 2026-09-09 — `converged` сверяет spec-delta added/modified/removed с `docs/spec/**`; S04 без spec-delta проходит; архив не merge |

### RM-018 — analyzed видит не только `CR-*` (F-008)

| | |
|---|---|
| Эффект | Claims O1/E1 и т.п. не теряются на `analyzed` |
| Минимум | Гейт/экстрактор принимает стабильные ID из request, не только префикс `CR-` |
| Слои | `fsm.py` / intake schema |
| Критерии | `SPEC-001`, `PROC-001` |
| Acceptance | Репро S02 r2: O1/E1 в request → analyzed pass при полном coverage |
| Regression | По-прежнему 100% mapped claims. Не золотить extra поля routing (AB-05 — отдельно) |
| Стоимость | S |
| Зависимости | нет |
| Статус | **done** 2026-09-09 — экстрактор берёт bullet `O1`/`E1` и `CR-*`; slice schema допускает те же ID; 100% coverage mapping без extra routing fields |

---

## P2 — стоимость процесса при рабочем обходе

### RM-020 — профиль ширины вызова (Q-001; флаги lock из Q-007)

| | |
|---|---|
| Эффект | Analyze/фаза не требуют один LLM-ответ на все артефакты; 27B+ не обязан 3 RTT |
| Минимум | lock `narrow|medium|wide`; `analyzed` только если routing+slices+coverage на диске; split записи opt-in. Routing первым шагом **сохранить** (AB-03) |
| Слои | lock.yaml, FSM подшаги; **не** копия skill на ornith |
| Критерии | `PROC-004`, `PROC-007` |
| Acceptance | narrow: три записи, гейт после комплекта. wide: один шаг тоже может закрыть analyzed. S02 без калибровочных extras |
| Regression | Не skip Specify для tiny (BM-01). Не вшивать A09_ANALYZE_FOCUS как единственный режим |
| Стоимость | L |
| Зависимости | RM-002 желателен; **после** RM-010, иначе режем пустой spec |
| Статус | **done** 2026-09-09 — lock/config `workflow.call_width` `narrow\|medium\|wide` (default wide); `analyzed` только при routing+slices+coverage; split opt-in; routing первым; `auto_accept_decisions` не обходит Human Gate |

### RM-021 — маршруты docs \| ops \| code (Q-005 + Q-006)

| | |
|---|---|
| Эффект | S08b/S08c не требуют `limiter.py` и Red pytest по коду |
| Минимум | Один вид Change: `code` (как сейчас) / `docs` / `ops`. docs/ops: `allowed_paths` вне src; Verify трассировки/файлов без Target Red по коду |
| Слои | routing schema, FSM, task schema |
| Критерии | `SPEC-006`, `CODE-002`, `PROC-003` |
| Acceptance | Фикстура S08b: только spec, без правки limiter. S08c: ops файлы, spec/src не обязаны меняться. S02/S03 **без** этого маршрута |
| Regression | Не ослабить Implement для code Change. Hidden code suite не применяется к docs-only |
| Стоимость | L |
| Зависимости | **RM-010** (иначе vacuous specified) |
| Статус | **done** 2026-09-09 — `route: code\|docs\|ops` (нет поля = code); docs/ops allowed_paths вне src/tests; targeting file/schema oracle; implemented без обязательного product regression; hidden suite только для code |

### RM-022 — не хардкодить «один SLICE» + unknown keys (AB-02, AB-05)

| | |
|---|---|
| Эффект | Multi-cap получает ≥2 среза без frozen extra; routing не падает на лишний `schema_version` |
| Минимум | (1) убрать/не класть в канонический skill extra «пиши только SLICE-01»; (2) игнорировать неизвестные ключи верхнего уровня routing **или** зафиксировать schema и клиентский strip в CLI |
| Слои | skill extra / CLI parse; schema |
| Критерии | `SPEC-005`, `PROC-002` |
| Acceptance | A10-02 класс: без extra → 2 slice files на S05 routing. Лишний ключ не валит analyzed |
| Regression | Routing.yaml обязателен. Не считать 2 slices достаточным для live spec (нужен RM-010) |
| Стоимость | S–M |
| Зависимости | нет для (2); (1) не путать с патчем A09 prompts |
| Статус | **done** 2026-09-09 — skill: один slice на primary capability; routing top-level `additionalProperties: true` (лишний `schema_version` не валит analyzed); 2 slices ≠ live spec |

---

## P3 — удобство, не ядро

### RM-030 — `analysis.md` optional (AB-04)

| | |
|---|---|
| Эффект | Skill не требует summary, которого гейт не проверяет |
| Минимум | Docs/skill: analysis.md необязателен; `analyzed` = routing+slices+coverage |
| Слои | skill/docs |
| Acceptance | Пакет без analysis.md проходит analyzed, если три артефакта валидны |
| Regression | Новый LLM **not-tested** — не блокировать P0 |
| Стоимость | S |
| Зависимости | нет |

### RM-031 — EARS как стиль spec; optional PBT (PP-04, KI-07)

| | |
|---|---|
| Эффект | Короче проверяемые формулировки; больше входов теста **без** замены hidden suite |
| Минимум | Гайд в `docs/spec` / SPEC-003: WHEN/SHALL рядом с RFC 2119. PBT — optional Target, локальный runner, не генератор Kiro |
| Слои | docs; optional tests |
| Acceptance | Редакционный: новые req в гайде. PBT: отдельный Change, skip если нет runner |
| Regression | Не `.kiro` файлы; не ослаблять F-010; не Cucumber |
| Стоимость | S (EARS) / M (PBT) |
| Зависимости | RM-010 для смысла SHALL |

---

## Вне шкалы (явно не делать)

| Источник | Почему нет RM |
|---|---|
| Q-003 embeddings | defer; не F-003 |
| Q-004 LLM считает токены | reject |
| Q-007 constitution.md | defer; флаги в RM-020 |
| Slash-SDD, OpenSpec fluid, BMAD auto, Kiro Quick Spec | A11; ядро не заменять |
| F-007 thinking | mitigated `--reasoning off` |
| Analog live rank | not-tested A11-06 |
| Снятие Human Gate / hidden suite | A10-01: не улучшение |

---

## Неизвестные после roadmap

Verify/Archive на ornith после RM-010+; interrupt S10; F-006 на живой серии Changes; analog на `:1240`; `usage` tokens в harness; GPU-only 8 GB; другие модели; mutation score продукта (A07-03).

Повторный holdout A09 **не** начинать, пока не закрыты RM-010 и RM-009 (иначе снова F-010/F-009).
