# Сводка анализа DeltaFuse (A12-02)

Дата: 2026-09-08. Карточка [A12-02](packets/A12-02.md). Покрытие слоёв: [matrices/coverage.md](matrices/coverage.md).

**Объект.** Фреймворк в этом репозитории (аудит с ревизии `60ea404`, VERSION `2.0.0`) и установка в изолированные тестовые продукты. Прикладной продукт родителя не SSOT.

**SUT результата работы.** Только `ornith-1.5-35b-a3b` Q4_K_M, llama-server `:1240`, `--reasoning off`. n=3 — пилот. Имя A3B **не** доказывает GPU-only в 8 GB. Mock eval **не** успех модели. Живой ранг аналогов vs ornith **not-tested** ([A11-06](experiments/A11-06/result.md)).

Три слоя: нормативная модель (docs/skills/схемы) ≠ CLI/FSM ≠ качество на ornith. `A01 pass` = критерий определён.

Roadmap с acceptance — [A12-03](packets/A12-03.md) после parking [A12-04](packets/A12-04.md). Здесь — ответы и ядро, не внедрение.

---

## Вопрос 1. Назначение и ограничения

**Вопрос владельца.** Какие классы запросов и профили моделей реально поддерживаются, где границы.

**Вердикт.** Нормативная модель описывает полный Change-цикл (Intake→Archive) для потока человеческих запросов в spec + код + тесты. На измеренном локальном профиле цикл **не** устойчив: holdout 11/11 `fail`, 0 `converged`. Формального лимита TASK недостаточно (F-002, F-010, борозда Analyze).

**Уверенность.** Высокая для границ этого SUT (A09-13). Низкая для других моделей/квантований.

**Предел.** Не переносить вывод на Copilot/Claude/Opus, thinking-on, 14B, или «8 GB GPU-only».

### Что держится на этом SUT

| Класс | Case | Вердикт | Evidence |
|---|---|---|---|
| Неоднозначный запрос → Human Gate | S04 | **pass** | 3/3 `blocked-on-decision` + DEC; AB-06 |
| Tiny capability / bugfix *с калибровочными extras* | S02 / S03 | **partial** | Implement Green, hidden 2 passed; 0 Verify; S02 F-008/F-009 |
| Недоверенный Intake | S12 intake | **pass** (фаза) | инъекция отброшена; Specify всё равно F-010 |
| Терминал duplicate | S09 r1 | **pass** 1/3 | r2/r3 без terminal |

### Что не поддерживается на этом SUT

Пустой продукт (S01), multi-cap + policy (S05), длинный вход / крупный каталог (S06/S07), refactor / docs-only / ops (S08), серия Changes и удаление (S11), interrupt (S10 **not-run**), сквозной Verify/Archive. Типичный стоп — **F-010** (`specified` без live spec).

### Профиль модели

Рабочий путь: голый llama-server, reasoning **off**. Studio thinking-on — F-007 (mitigated сменой SUT, не патчем skill). VRAM вызова ~4.2–5.5 / 8.2 GiB; веса ~20 GiB в RAM. Фактический tokenizer budget A09 **not-tested** (`usage: {}`). Порог PROC-007 «шаг ≤120 с» обычно да, Decompose до 147 с.

---

## Вопрос 2. Практики разработки и архитектурные ошибки

**Вопрос владельца.** Инварианты, способы обхода, восстановление, сопровождение.

**Вердикт.** Ядро FSM и независимый oracle **сильнее** slash-SDD (A10-01). Дыры гейтов и учёта контекста дают ложное «соответствие» (P0) и неbounded execution (P1). Восстановление после interrupt на ornith **не** измерено.

**Уверенность.** Высокая для framework-findings (контрпример в коде/тестах). Средняя для ornith-специфичных F-008/F-009 (n=3, extras).

**Предел.** Контракт Verify существует (A02-08); на SUT почти не упражнялся.

### Инварианты, которые стоит сохранить

Typed `TASK-*` + DAG + `allowed_paths`; Human Gate DEC (не auto-accept); Specify не читает `src/**`; `docs/spec/**` закон **до** кода; hidden/pytest не self-review; archive только после `converged`, T8 no-overwrite; RFC 2119; GWT в TASK; T1–T8 evidence/FSM; routing.yaml первым шагом Analyze (AB-03).

### Обходы и дефекты (не гипотезы)

| ID | Класс | Суть | Приоритет плана |
|---|---|---|---|
| F-010 | P0 | `specified` без живых путей spec | ложное соответствие, потеря intent |
| F-009 | P0 | неаутентичный Red / private после overshoot | ложный TDD |
| F-004 | P0 | path traversal / silent skip | повреждение границы repo |
| F-006 | P0 | stale Green при смене spec | ложный converge; SUT **not-run** |
| F-001 | P1 | CRLF → lock hash | сопровождение Windows |
| F-002 | P1 | `PHASE_CONTRACTS` мёртв; нет task `context_budget` | bounded execution |
| F-003 | P1 | `words * 1.3` | ложный pass бюджета |
| F-005 | P1 | `cancelled`/`superseded` ломают `converged` | восстановление/переразбор |
| F-008 | P1 | analyzed видит только `CR-*` | маршрутизация claims |

F-007 не текущий блокер `:1240`.

### Восстановление и сопровождение

Статика: A05-03 / A06-03/04 **pass**. S10 interrupt **not-run**. F-001 ломает bash smoke и кросс-платформенный hash. F-003/F-002 делают lint-context недостоверным.

---

## Вопрос 3. «Лучшее / лишнее / худшее» у аналогов

**Вопрос владельца.** Доказательные решения: сохранить, адаптировать, удалить, не переносить.

**Вердикт.** Не заменять ядро DF на Spec Kit, OpenSpec, BMAD или Kiro. Дешёвый SDD на **том же** SUT даёт файлы, не hidden-green (A10-01) — это не улучшение. Качество analog-продуктов vs ornith **не** ранжировать (A11-06).

**Уверенность.** Высокая для контрактных отказов (гейты, SSOT, oracle). N/A для «кто пишет лучше код».

**Предел.** Pins: Spec Kit v1.0.4, OpenSpec v1.12.0, BMAD v6.12.0, Kiro docs 2026-08-27. Шаблоны **не копировать** без отдельного решения и license notice.

### Сохранить своё

FSM + typed tasks; Human Gate; независимый Verify/hidden; Specify-time SSOT (не merge на archive); изоляция Specify от `src/**`; фазы + Maintainer (не каталог персон); `DEC-*`; RFC 2119; GWT; протокол A07-03 (не вендор PIT).

### Адаптировать (фиксы, не заимствование продукта)

`.gitattributes` / LF (F-001); `converged` принимает `cancelled`/`superseded` (F-005); `is_relative_to` (F-004); усилить гейт `specified` (F-010, AB-01) — **исследовать** как изменение DF, не чеклист Spec Kit.

### Исследовать (гипотезы → A12-04)

Профили ширины/lock (Q-001, BM-01); constitution-как-lock (Q-007); EARS как *стиль* spec (KI-02, PP-04); optional PBT (KI-07, PP-06); пост-Verify сверка delta↔live spec (Q-008); extra Analyze «1 slice» упростить (AB-02); `analysis.md` optional (AB-04).

### Не переносить / удалить как идею замены

Slash-SDD и converge-без-oracle; fluid «no gates»; SSOT только после кода; Quick Spec; Design-First как Specify; `bmad-build-auto` / Loop; self-review как Verify; `.kiro/` SSOT; parallel task waves на 8 GB; каталог 157 extensions; Pact; Cucumber; PIT в ядре; ITIL-CMDB.

**Худшее для этого продукта:** снять Human Gate или независимый oracle ради скорости (A10-01 S02 r3: свои тесты pass, hidden fail).

---

## Вопрос 4. Другие существенные улучшения

**Вопрос владельца.** Приоритизированный backlog с эффектом и ценой.

**Вердикт.** Сначала **исправления ошибок** (F-*), не гипотезы Q-* и не analog-шаблоны. P0 не усреднять с P3. Полный roadmap с acceptance/regression — A12-03 после A12-04.

**Уверенность.** Высокая для P0/P1 findings. Низкая для Q-001…Q-008, пока A12-04 не вынес `accept`/`reject`.

### Исправления (не гипотезы)

| Приоритет | Что | Ожидаемый эффект | Цена (грубо) |
|---|---|---|---|
| P0 | F-010: `specified` требует live paths из delta | holdout Specify перестаёт быть vacuous | FSM + тесты гейта; не skill-промпт |
| P0 | F-009: аутентичный Red / запрет private | Target не закрывает overshoot | schema/FSM Target; hidden suite остаётся |
| P0 | F-004: каноникализация путей | нет чтения вне repo | `integrity.py` + fuzz |
| P0 | F-006: stale evidence | нет silent Green после смены spec | hash ревизии на evidence |
| P1 | F-001 `.gitattributes` | bash + lock hash | один файл |
| P1 | F-002/F-003 enforcement + tokenizer | честный budget | FSM + adapter (Q-002) |
| P1 | F-005 terminals на `converged` | отмена задач не клинит пакет | `fsm.py` |
| P1 | F-008 claims не только CR-* | Analyze видит O1/E1 | гейт analyzed |

### Недоказанные гипотезы (не внедрять в A12-02)

Q-001 борозда; Q-002 tokenizer (частично уже F-003); Q-003 embeddings — **не** фикс F-003; Q-004 вложенный «посчитай токены» — кандидат **reject**; Q-005 docs-only; Q-006 ops files; Q-007 constitution-lock; Q-008 post-Verify merge check.

### Улучшения процесса (P2–P3, после P0)

Упростить frozen extra «только SLICE-01» (AB-02); `analysis.md` optional (AB-04); EARS-стиль в spec; optional PBT **не** вместо hidden suite.

---

## Минимальное ядро и расширения

**Ядро (не упрощать ради аналогов).** Change FSM и гейты; spec-delta → запись `docs/spec/**` до Implement; typed TASK + DAG + Red/Green evidence; Human DEC; независимый hidden/pytest; routing-first Analyze; RFC 2119 + GWT; T8 archive.

**Необязательно.** `analysis.md`; каталоги персон/extensions; PBT-раннер; constitution articles I–III; Clarify без снятия DEC; lock-профили ширины (если A12-04 `accept`); дата в пути архива (OS-04, если не ломает T8).

**Сильные стороны, которые аудит подтвердил.** S04 не срывается в Specify; S12 Intake не auto-accept; framework pytest 91 / ~8 с и T1–T8; S03 не портит верную spec; A10-01: независимый hidden обязателен.

---

## Неизвестные (явно)

Verify/Archive на ornith; interrupt S10; F-006 на SUT; analog live на `:1240`; tokenizer `usage`; GPU-only 8 GB; другие модели; mutation score продукта; лестницы S06/S11.

Parking Q-* не разобран — A12-04.
