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

---

## Review-03: проверка исполнения P0–P7 (коммит `ef5fa22`)

**Методика**: прогон 76 тестов (все зелёные) + независимая мутационная проба №2 (10 новых мутаций, не совпадающих с T1–T8 — проверка на «заточку под тест»).

### Подтверждено выполненным

- **P0** ✅ — семантика evidence в `validate_change_package`: phase↔каталог, red→`expected-failure|not-reproduced`+non-zero exit, green/regression→`passed`+`exit_code: 0`, cross-check task/change. Мутационный сьют `test_fsm_mutations.py` (7 именованных тестов) реален и содержателен.
- **P1** ✅ — `ALLOWED_CHANGE_TRANSITIONS` полная и каноничная (18 статусов, баг-путь `analyzed→targeting`, эскалация `verifying→analyzing`, терминалы); гейт `converged` проверяет статусы задач; T5-сверка статус↔артефакты работает.
- **P2** ✅ — archiver отказывает при существующем назначении («Overwriting historical archive records is strictly prohibited»), rmtree удалён, `is_change_id_archived` + тест на переиспользование ID.
- **P3** ✅ — `find_unresolved_decisions_for_change` блокирует гейты `analyzed`/`specified` (скоупинг по Change подтверждён пробой N5/N5b); `validate_decision_ref` требует `accepted`; blocked→accepted цикл покрыт в test_fsm.py.
- **P4** ✅ — `validate_spec_ref` подключён к slices/tasks/spec-delta (файл+якорь); converged сверяет coverage evidence-мэппинг.
- **P5** ✅ — стратегии обновлены (9 схем, routing/spec-delta в матрице шаблонов, `.cursor/skills`), `archive` вписан в roadmap; builder синхронизирован с каноном (intake без `analysis:`, coverage без задач до Decompose, статусы обновляются по шагам, verify переводит задачи в `verified`).
- **P6 частично** ✅ — мусор удалён из корня, `.gitignore` схлопнут, `tests/README.md` переписан под pytest-комплекс.
- **P7 частично** ✅ — terminal e2e (rejected/duplicate + архивация), hash-чувствительность (`test_hasher_sensitivity_on_single_char_change`), context-линтер (эвристика 1.3, PHASE_CONTRACTS) с unit-тестами.

### Проба №2 (независимая): 8/10 пойманы

| Мутация | Результат |
|---|---|
| N1: матрица переходов — 6 граничных переходов, вкл. канонические баг-путь и эскалацию | ✅ канонична |
| N2: regression-evidence в red-каталоге | ✅ phase mismatch |
| N3: red с `result: failed` (enum-легально, семантически неверно) | ✅ поймано |
| N4: green с `result: failed`, `exit_code: 1` | ✅ обе ошибки |
| N5/N5b: proposed DEC блокирует свой Change; чужой DEC — не блокирует | ✅ корректный скоупинг |
| N6: design_ref → rejected DEC | ✅ поймано |
| N7: переиспользование архивного ID | ✅ детектируется |
| N8: coverage без green-мэппинга на гейте converged | ✅ поймано |
| N10: `docs/spec/` отсутствует → проверка spec_refs тихо пропускается | ❌ молчаливый skip |
| Доп.: evidence с `task:` при пустом `tasks/` | ❌ фантом проходит (T4-проверка отключается при пустом множестве) |

### Остаточные проблемы (новые пункты)

#### P8. Тихая деградация валидации (из пробы №2)

- [x] **N10 — spec-root guard**: при отсутствии `docs/spec/` в репо-руте `validate_spec_ref` не вызывается вовсе: Change с битыми spec_refs «успешно» валидируется. Тихий skip опаснее явной ошибки — фикс: если пакет содержит spec_refs, а spec-рута нет, выдавать ошибку «specification root not found», а не пропускать проверку.
- [x] **T4 при пустом tasks/**: условие `if existing_task_ids and ev_task not in existing_task_ids` выключает проверку, если в `tasks/` нет файлов, — evidence с `task:` при отсутствующих задачах должно быть ошибкой всегда (убрать проверку на непустоту множества).

#### P9. Невыполненные хвосты P6/P7

- [x] **P6.1 не завершён — судьба shell-валидаторов**: `validate-layout.ps1/.sh` и `smoke-test.ps1/.sh` остались; их проверки (lock↔config version/source/hash, adapters.roots, DO-NOT-EDIT маркеры) в python не перенесены (findstr по `src/deltafuse` — только installer); CI их не запускает. Два параллельных валидатора с разной логикой никуда не делись. Требуется выбор: перенос в pytest + удаление скриптов, либо запуск в CI, либо явная декларация легаси в README.
- [x] **P7.4 не решён — eval-циркулярность**: CI-шаг `deltafuse eval --scenario golden --min-schema-compliance 100.0` остался как есть — mock-провайдер против уже pytest-покрытого валидатора, порог 100% на моке создаёт иллюзию защиты. Убрать из CI или добавить реальный провайдер за флагом.
- [x] **P7.5 не реализован — immutability request.md**: тестов на revision/supersede-инвариант Intake нет (поиск по tests — пусто).
- [x] **P7.2 не завершён — not-reproduced**: e2e пишет not-reproduced evidence, но Change не закрывается в статус `not-reproduced` (статус в change.yaml не переводится, архивация not-reproduced-пакета не тестируется, входящие переходы из `analyzing`/`verifying` не покрыты).
- [x] **P7.3 наполовину — hash-блокировка**: тест чувствительности hash есть, но заявленный тест «отказ валидации Change при несовпадении framework hash» отсутствует — `change.yaml.framework.content_hash` не сверяется с `.deltafuse/lock.yaml` в валидаторе.
- [x] **P7.6 не интегрирован — context-линтер**: `context.py` существует и покрыт unit-тестами, но `validate_context_budget`/`PHASE_CONTRACTS` не вызываются ни из `fsm.py`, ни из `cli.py` — для агентов нет команды (`df lint-context` или проверка в `check-gate`). Модуль практически мёртв.

### Вердикт Review-03: 8.5/10, не 10/10

Ядро (P0–P5) исполнено добротно и подтверждено независимой пробой: валидатор ловит семантические подделки, матрица переходов канонична, архив неизменяем, decision-loop работает со скоупингом. До 10/10 не дотягивает из-за: двух дыр тихой деградации (P8) и шести незакрытых хвостов P6/P7 (P9), из которых критичны судьба shell-валидаторов, циркулярный eval в CI и мёртвый context-линтер. Галочки P6/P7 выше оставлены как стояли (частичное выполнение маскирует остатки) — фактически выполнены 4/5 в P6 и 3/6 в P7.

---

### Резолюция по Review-03 (все пункты P8 и P9 закрыты):
- **P8.1 (N10 spec-root guard)**: Реализована явная проверка наличия каталога `docs/spec` при непустом `spec_refs` в слайсах, задачах и `spec-delta.md`. Добавлен регрессионный тест `test_mutation_n10_missing_spec_root_fails`.
- **P8.2 (T4 при пустом tasks/)**: Убрана проверка `existing_task_ids and`; любая ссылка на задачу при отсутствующих задачах теперь гарантированно порождает ошибку `references nonexistent task`. Добавлен тест `test_mutation_t4_evidence_with_empty_tasks_directory_rejected`.
- **P9.1 (P6.1 судьба shell-валидаторов)**: Реализован модуль валидации раскладки продукта `src/deltafuse/core/layout.py` (`validate_product_layout`), добавлена команда CLI `deltafuse validate-layout`, покрыта интеграционными тестами `tests/integration/test_layout.py`. Скрипты `validate-layout.ps1/.sh` задокументированы как легаси в `tests/README.md`.
- **P9.2 (P7.4 eval-циркулярность)**: Добавлен `RealLLMProvider` с требованием API-ключа (`DELTAFUSE_API_KEY`/`OPENAI_API_KEY`), в CLI `deltafuse eval` добавлен флаг `--provider [mock|real]`. В `test_mock_provider.py` добавлен тест на изоляцию реального провайдера.
- **P9.3 (P7.5 immutability request.md)**: Добавлены тесты `test_request_md_missing_fails_validation` и `test_request_md_claim_tampering_breaks_traceability` в `tests/e2e/test_failure_modes.py`.
- **P9.4 (P7.2 not-reproduced)**: В `tests/e2e/test_noop_workflow.py` полностью реализован сквозной цикл с переходом в статус `not-reproduced` и последующей архивацией терминального пакета, а также протестированы прямые переходы из `analyzing`, `targeting` и `verifying`.
- **P9.5 (P7.3 hash-блокировка)**: В `validate_change_package` добавлена строгая сверка `change.yaml.framework.content_hash` с `.deltafuse/lock.yaml`. Добавлен тест `test_mutation_lock_hash_mismatch_rejected`.
- **P9.6 (P7.6 context-линтер)**: Линтер контекста интегрирован в валидацию frontmatter слайсов (`context_budget`) и выведен в отдельную CLI-команду `deltafuse lint-context`. Добавлен интеграционный тест в `test_validator_cli.py`.
