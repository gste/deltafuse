# Результат эксперимента A07-01

- **ID карточки:** A07-01
- **Ревизия:** `16166fa`
- **Критерии:** `TEST-001` (Fault Detection Power), `TEST-004` (TDD Red Authenticity), `PROC-002` (FSM Determinism)
- **Вердикт:** **pass** (достоверность семантических правил для Red/Green evidence, дифференциация статусов и кодов возврата подтверждены)

## Ожидаемое поведение

1. **Достоверность фазы Red (TDD Red Authenticity)**:
   - Падение теста на фазе Target (`evidence/red/<task-id>.yaml`) должно быть строго поведенческим: `result: expected-failure` (или `not-reproduced`), `exit_code != 0`.
   - Попытка зарегистрировать зелёный тест (`result: passed`, `exit_code: 0`) или подложить green-отчёт в каталог `evidence/red/` должна блокироваться валидатором FSM (мутационные инварианты T1 и T2).
2. **Достоверность фазы Green и Regression**:
   - На фазах Implement и Verify свидетельства (`evidence/green/`, `evidence/regression/`, `evidence/verification/`) обязаны иметь `result: passed` и `exit_code: 0`.
3. **Защита от фиктивных свидетельств**:
   - Каждое свидетельство обязано быть привязано к существующему Change ID и Task ID. Фиктивные свидетельства (на несуществующие задачи или при пустом каталоге `tasks/`) отвергаются (инвариант T4).
4. **Разграничение категорий ошибок**:
   - Схема `evidence.schema.yaml` поддерживает поле `failure_category` (`behavioral-mismatch` vs синтаксические ошибки), позволяя отделять реальное отсутствие функционала от поломки фикстуры или окружения.

## Наблюдаемое поведение

1. **Семантическая верификация мутаций T1, T2, T4**:
   - `test_mutation_t1_green_evidence_in_red_folder_rejected`: файл с `phase: green` внутри каталога `evidence/red/` отклонён:
     `phase mismatch (file in 'red/' has phase 'green')`.
   - `test_mutation_t2_red_evidence_with_passed_result_rejected`: файл в `evidence/red/` с `result: passed` и `exit_code: 0` отвергнут:
     `red evidence must have result 'expected-failure' or 'not-reproduced'` и `red evidence must have non-zero exit_code (got 0)`.
   - `test_mutation_t4_evidence_for_nonexistent_task_rejected`: файл свидетельства на задачу `TASK-999` отвергнут:
     `references nonexistent task 'TASK-999'`.
2. **Контроль гейтов жизненного цикла**:
   - `check_gate('targeting')` требует обязательного наличия валидных Red-свидетельств в `evidence/red/`.
   - `check_gate('implemented')` требует одновременного наличия Green-свидетельств в `evidence/green/` и регрессионных свидетельств в `evidence/regression/`.
   - `check_gate('converged')` требует сквозного прогона верификации `evidence/verification/run.yaml` с `exit_code: 0`.
3. **Оценка устойчивости к ослаблению assertions**:
   - FSM гарантирует, что фаза Red фиксирует падающий тест на неизменённом коде реализации.
   - В сочетании с критерием `CODE-002` (проверка `allowed_paths` и `forbidden_paths`) и `TEST-002` (Black-box oracle) исключается возможность ослабления ассертов теста агентом без фиксации изменения в git diff задачи.

## Ограничения

- FSM валидирует структуру свидетельств (`exit_code`, `result`, `phase`, привязку к задаче). Сам факт физического выполнения команды в тестовом окружении гарантируется рантаймом агента/CI (проверяется в A07-02 на тестовом наборе фреймворка).
- Ранее в задаче A05-04 зафиксирован дефект [F-006](../../findings/F-006.md) (отсутствие привязки свидетельства к git commit hash `base_revision`, что позволяет устаревшим свидетельствам проходить гейт при конкурентных мержах). В рамках текущего контракта схем проверка структурной и семантической достоверности работает штатно.

## Handoff

- **Результат**: Правила валидации Red/Green evidence подтверждены на уровне схемы, FSM и мутационных тестов.
- **Готовность к переходу**: Разрешён переход к задаче [A07-02](packets/A07-02.md) — «Измерить полезность тестов фреймворка».
