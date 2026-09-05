# Backlog

Unchecked items are active work. Items marked `[x]` are verified as done.
Basis: [testing review results](docs/testing-review-results.md) — ревью планов тестирования и мутационная проба (7/8 семантических дефектов не пойманы валидатором).
Sverка с внешним планом: [BACKLOG-TESTING.md](BACKLOG-TESTING.md) — проанализирован, подтверждён, поглощён пунктами ниже (см. «Сверка BACKLOG-TESTING.md» в конце файла).

---

## P0. Семантическая валидация evidence (закрывает мутации T1–T4)

Главная дыра: гейты этапов Target/Implement проверяют существование YAML-файлов, но не их семантику. Подделанный Red (зелёный файл в красном каталоге) проходит.

- [x] В `fsm.py` (гейт `targeting`): каждый YAML в `evidence/red/` обязан иметь `phase: red` и `result: expected-failure`. Файл с `phase: green`/`result: passed` в red-каталоге — ошибка валидации.
- [x] Гейт `implemented`: каждый YAML в `evidence/green/` и `evidence/regression/` — `phase` соответствует каталогу, `result: passed`, `exit_code: 0`.
- [x] Cross-check `evidence.task` ↔ существующий `tasks/TASK-NNN.md` (фантомная TASK-999 — ошибка).
- [x] Cross-check `evidence.change` ↔ `change.yaml.id`.
- [x] Выделенный мутационный сьют `tests/unit/test_fsm_mutations.py` с именованными регрессионными тестами по образцу пробы из ревью: `test_mutation_t1_green_evidence_in_red_folder_rejected`, `test_mutation_t2_red_evidence_with_passed_result_rejected`, `test_mutation_t3_converged_gate_fails_with_pending_tasks`, `test_mutation_t4_evidence_for_nonexistent_task_rejected`, `test_mutation_t5_status_mismatch_rejected`, `test_mutation_t7_broken_spec_anchor_rejected`, `test_mutation_t8_rearchive_collision_fails`. T6 не включается — уже ловится существующими тестами (coverage completeness). *(Дополнение из BACKLOG-TESTING.md.)*

## P1. Согласованность состояний (закрывает T3, T5)

Валидатор не сверяет заявленные статусы с фактическим наполнением пакета.

- [x] Реализовать матрицу переходов Change (сейчас `VALID_CHANGE_STATUSES` — мёртвый код): таблица допустимых переходов по канону `docs/state-machine.md`, включая `specification-proposed` и `blocked-on-decision` (их нет в текущем списке — расходится с каноном на 2 статуса).
- [x] Гейт `converged`: все task frontmatter в статусах `implemented|verified` (не `pending`/`targeting`/`draft`); после гейта — перевод задач в `verified` (см. workflow.md §7).
- [x] Сверка `change.yaml.status` с артефактным наполнением: например, `status: decomposed` без `tasks/*.md` — ошибка; полный пакет при `status: normalized` — предупреждение/ошибка.
- [x] Тесты «недопустимый переход» (`normalized → converged` и др.) — позитивная и негативная матрица по таблице переходов из state-machine.md.

## P2. Архив: идемпотентность и сохранность истории (закрывает T8)

`archiver.py` молча перезаписывает существующий архив (`shutil.rmtree`) — прямая потеря истории.

- [x] Отказ архивации с понятной ошибкой, если `docs/archive/changes/<date>-<change-id>/` уже существует (никакого rmtree).
- [x] Решение по предложенному в BACKLOG-TESTING.md флагу `--overwrite`: **отклонить** — разрушаемый архив противоречит инварианту неизменности истории (proposal invariant 28–29); escape-hatch демпфирует защиту. Если понадобится — только через явное ручное вмешательство человека, не флагом CLI.
- [x] Тест повторной архивации того же ID в тот же день → `ArchivalError`.
- [x] Тест: архивированный пакет не изменяется при повторном прогоне.
- [x] Инвариант Intake «не переиспользовать архивные CHG-ID»: проверка нового Change-ID против `docs/archive/changes/` + тест.

## P3. Decision Convergence Loop — нулевое покрытие (ядро процесса)

Ни один тест не создаёт DEC-файл; гейт `specified` не смотрит на решения.

- [x] Реализовать проверку в гейте `specified` (и `analyzed`): незакрытые `DEC-*` со `status: proposed`, затрагивающие Change → блокировка (канон: `blocked-on-decision`).
- [x] E2E-сценарий blocked-on-decision: Analyze → создаётся DEC proposed → гейт blocked → человек принимает (accepted) → re-analyze → гейт открыт. Фикстура по roadmap этапа 4 (`fixture_blocked_on_decision`) — запланирована, но не создана.
- [x] Набор 2.3 стратегии: `design_ref` → существующий DEC в статусе `accepted` (proposed/rejected — ошибка).
- [x] Инвариант «decision change: null для Bootstrap» уже в схеме — добавить позитивный тест с `change: null`.

## P4. Целостность ссылок: подключить уже написанное (закрывает T7)

`find_spec_anchors` реализован и покрыт unit-тестами, но не вызывается валидатором.

- [x] Вызвать проверку якорей в `validate_change_package`: каждый `spec_refs` из task/slice/spec-delta/coverage → файл существует и якорь `REQ-*`/`SC-*` физически присутствует в `docs/spec/**` (пути — из `.deltafuse/config.yaml`).
- [x] Негативный тест: spec_refs на несуществующий файл/якорь → ошибка.
- [x] Гейт `converged`: каждый claim coverage.yaml имеет заполненные `evidence.red/green/regression` (сейчас проверяются только файлы в каталогах, без сверки с матрицей).

## P5. Актуализация планов и канона (закрывает Д1–Д3 планов)

- [x] Обновить `docs/testing-strategy.md` и `docs/testing-roadmap.md`: 9 схем вместо 7 (добавить routing, spec-delta); убрать `.cursor/rules/` (факт: `.cursor/skills`); FSM-матрицу стратегии привести к таблице переходов `docs/state-machine.md` (включая баг-путь `analyzed → targeting` без Decompose — сейчас в стратегии невозможный маршрут).
- [x] Синхронизировать фикстуры с каноном: `MockChangeBuilder.step_intake` не должен писать `analysis: {routing, summary}` на этапе Intake (analysis заполняется после Analyze); coverage.yaml не должен упоминать задачи до Decompose. Сейчас фикстуры кодируют неверную модель, которую валидатор легитимирует.
- [x] Вписать команду `archive` в roadmap этап 3 (сейчас она «протекает» — используется в этапе 4, но нигде не запланирована).

## P6. Судьба shell-валидаторов и гигиена (закрывает Д9 и мусор)

- [x] Решить судьбу `validate-layout.ps1/.sh` и `smoke-test.ps1/.sh`: либо (а) удалить после переноса их проверок (config/lock/adapters/DO-NOT-EDIT маркеры) в python-валидатор + pytest, либо (б) оставить и добавить их запуск в CI. Сейчас два параллельных валидатора с разной логикой, CI гоняет только pytest.
- [x] Перенести в python при выборе (а): проверка lock ↔ config (version, source, hash), adapters.roots из config, DO-NOT-EDIT + hash-маркеры сгенерированных скиллов.
- [x] Удалить мусор из корня: `_builder.py`, `build_evals.py`, `run_setup.py`, `test_b64.txt`, `build/`; добавить `.pytest_cache/` в `.gitignore`.
- [x] `.gitignore`: секция Python задублирована (`# Python` и `# Python / Testing` повторяют `__pycache__/`, `*.py[cod]`, `*$py.class`) — схлопнуть. *(Уточнение из сверки BACKLOG-TESTING.md: сам пункт «добавить build/, .pytest_cache/, *.pyc» уже выполнен.)*
- [x] Обновить `tests/README.md`: описать pytest-комплекс (unit/integration/e2e/evals, CLI, CI), сейчас описаны только shell-скрипты.

## P7. Углубление покрытия терминальных путей и evals

- [x] E2E: Change → `rejected` (out-of-scope на Analyze) и → `duplicate` — фиксация статуса, отсутствие последующих артефактов, архивация терминального пакета.
- [x] E2E: `not-reproduced` как полный сценарий: закрытие Change в статус `not-reproduced` (сейчас e2e пишет только evidence, не закрывая Change), входящие переходы из `analyzing`/`targeting`/`verifying` (потребует P1 — матрицу переходов).
- [x] Hash-чувствительность: тест «изменение одного файла в `process/` меняет content_hash» + тест отказа валидации Change при несовпадении framework hash (roadmap набор 4.3).
- [x] Eval-контур: либо вынести mock-evals из обязательного CI-шага с порогом 100% (циркулярная проверка мока против уже покрытого валидатора), либо добавить реальный провайдер-интерфейс (API-вызов опционально, за флагом) — сейчас порог 100% на моке создаёт иллюзию защиты.
- [x] Тесты инвариантов Intake: request.md иммутабельность (claims не переписываются, только revision/supersede) — структурная проверка наличия `## Revision` при изменённых claims в истории коммитов или через snapshot-хэш.
- [x] Контекстный линтер (набор 5 стратегии): машиночитаемый Context Contract (допустимые каталоги чтения/записи по шагам) + подсчёт токенов эвристикой «1 слово ≈ 1.3 токена» без тяжёлых зависимостей (tiktoken отклонён — см. Д6 ревью), валидация против `max_tokens`/`max_files` из config.yaml. *(Конкретизация из BACKLOG-TESTING.md — закрывает Д5 и Д6.)*

---

## Выполнено ранее (архив ревью v2 redesign и Review-01/02)

- [x] Восстановление канонических документов и шаблонов, исправление пиннинга версий, adapters.roots, путей в AGENTS/CLAUDE/README (Review-01/02 — см. git history и docs/testing-review-results.md).
- [x] Этапы 1–4 тестового плана реализованы: SchemaRegistry + 57 тестов (unit/integration/e2e/evals), CLI (init/validate/check-gate/archive/eval), CI-матрица 3 OS × 5 Python — все зелёные.

---

## Сверка BACKLOG-TESTING.md (внешний план от 2026-09-05)

### Валидность: подтверждена

Все ключевые утверждения плана сверены с фактическим кодом и каноном и совпали:
- Мутации T1–T8 и их непойманность — воспроизведены пробой в ревью (testing-review-results.md, Часть 3); классификация совпадает.
- «`VALID_CHANGE_STATUSES` — мёртвый код без `specification-proposed`/`blocked-on-decision`» — подтверждено чтением fsm.py.
- «`find_spec_anchors` не подключён к `validate_change_package`» — подтверждено.
- «archiver молча перезаписывает архив через rmtree» — подтверждено чтением archiver.py.
- «9 схем вместо 7 в планах» — подтверждено (в `process/schemas/` 9 файлов).
- «мутационного сьюта test_fsm_mutations.py нет» — подтверждено (файл отсутствует).
- Состав мусора в корне подтверждён; gitignore частично актуальнее плана (см. ниже).

### Отличия и что НЕ перенесено (осознанно)

1. **Флаг `--overwrite` для архива (Фаза 3 BACKLOG-TESTING) — отклонён.** Разрушение архива противоречит инвариантам 28–29 proposal («изменение artifacts архивируются, а не уничтожаются»; «archive не входит в контекст, но сохраняется»). Escape-hatch в CLI делает защиту декоративной. Зафиксировано в P2.
2. **Формулировка «задачи обязаны иметь терминальный статус `verified` (или `implemented`)» — уточнена.** По канону (workflow.md §7, state-machine.md) `verified` ставится только на Verify; требовать его на входе в `converged` нельзя. В P1 зафиксировано: вход — `implemented`, после гейта — перевод в `verified`.
3. **Пункт gitignore «добавить build/, .pytest_cache/, *.pyc» из Фазы 5 — уже выполнен** (правки внесены после написания BACKLOG-TESTING); реальный остаток — дублирование секции Python, занесено в P6.
4. **T6 не включён в мутационный сьют** — coverage-completeness уже ловится существующими тестами (`test_failure_modes.py::test_orphan_claim_in_coverage_fails_gate`).
5. **Именованные тесты мутаций и токен-эвристика 1 слово ≈ 1.3 токена — приняты** (P0 и P7): конкретные имена тестов дают трассируемость к пробе, эвристика решает Д5/Д6 без tiktoken.

### Вердикт по BACKLOG-TESTING.md

План валиден, актуален на дату сверки и покрывает ~90% того же пространства, что BACKLOG.md, но структурно слабее в двух местах: (а) не содержит судьбы shell-валидаторов и циркулярного eval-контура (P6/P7 BACKLOG.md); (б) предлагает опасный `--overwrite`. Дополнения из него поглощены в P0/P2/P6/P7; сам файл оставлен как источник, дублем не является.
