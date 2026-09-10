# A02-08 — Проверить контракт Verify, Converge and Archive

**Verdict: `pass` для условий карточки.** На ревизии `60ea40438b0142797848356c660ab88286565e7d` (рабочий HEAD `219da96c0ec1f6b458ec76a481c787538a69c90a`) выполнена детальная сверка контракта седьмой фазы жизненного цикла — **Verify, Converge and Archive** — по сквозной цепочке «инвариант -> документация -> навык агента -> схема/шаблон -> runtime gate FSM / archiver engine -> юнит/мутационный тест».

Результаты сопоставления зафиксированы в разделе 10 матрицы [backlog/matrices/contracts.md](../../../matrices/contracts.md).

## Подтверждённые инварианты фазы Verify, Converge and Archive

1. **VER-01 (Терминальный статус всех задач Change, T3):** FSM контролирует (`fsm.py:441-451`), что при вызове гейта `converged` все задачи в каталоге `tasks/` имеют статус `implemented` или `verified`. Если хотя бы одна задача остаётся в статусе `pending`, схождение блокируется мутационным тестом T3 (`test_mutation_t3_converged_gate_fails_with_pending_tasks`).
2. **VER-02 (Полная трассируемость claims на evidence, P4):** Гейт `converged` проверяет (`fsm.py:456-469`), что каждый `claim` в файле `coverage.yaml` привязан к конкретным свидетельствам `green` и `regression`. Неполная трассировка ломает гейт.
3. **VER-03 (Обязательность verification run evidence и отчёта):** Для схождения обязательно физическое наличие аналитического документа `verification.md` и валидного свидетельства выполнения полного проверочного набора `evidence/verification/run.yaml` (`exit_code: 0`, `fsm.py:349-352`).
4. **VER-04 (Допустимый переход FSM в converged и archived):** Из `converged` разрешён единственный переход в `archived`. Из терминального состояния `archived` любые дальнейшие переходы запрещены (`ALLOWED_CHANGE_TRANSITIONS["archived"] = set()`).
5. **VER-05 (Неизменяемость архива и запрет перезаписи, T8):** Функция `archive_change` исключает `shutil.rmtree` над архивом: если директория с именем `YYYY-MM-DD-<change-id>` уже существует в `docs/archive/changes/`, выбрасывается фатальное исключение `ArchivalError` (мутационный тест T8).
6. **VER-06 (Защита от архивирования неконвергировавшего Change):** Архивирование пакета, не прошедшего гейт `converged` (или не находящегося в терминальном статусе `rejected`, `duplicate`, `not-reproduced`), физически блокируется проверкой `check_gate(cpath, "converged")`.

## Наблюдения и итог по жизненному циклу

- **Математическая строгость схождения:** Жизненный цикл DeltaFuse закрывает Change не по факту «все файлы созданы», а по строгому аудиту полной трассируемости: `request -> claims -> routing/slices -> requirements -> tasks -> red/green/regression evidence -> verification.md -> immutable archive`.
- **Итог сопоставления семи фаз:** Все 7 фаз жизненного цикла успешно сопоставлены в разделах 4–10 матрицы `contracts.md`. Все FSM-гейты и мутационные защитные тесты T1–T8 подтверждены в коде и тестах ядра.

## Handoff

- **Фаза Verify, Converge and Archive верифицирована:** инварианты VER-01..VER-06 подтверждены и занесены в [backlog/matrices/contracts.md](../../../matrices/contracts.md).
- **Следующая задача по очереди:** [A02-09 — Проверить обходы gate и terminal paths](../../packets/A02-09.md) (исследование терминальных путей `rejected`, `duplicate`, `not-reproduced`, `superseded` и обходов гейтов).