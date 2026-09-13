# QF-022 — результат исполнения

- **Статус:** выполнено
- **Базовый commit (parent):** `c098438f45766277873428ae8f232347916f6ebb` (QF-021)
- **Итоговый commit:** тот, в котором лежит этот файл (child of base)
- **Инструменты:** Python 3.12.14 (.venv, CPython), pytest 9.1.1, Windows
  10.0.26200 (win32)
- **Red evidence:** `tests/unit/test_threshold_governance.py` на базовом
  commit — коллекция падала `ModuleNotFoundError: threshold_governance`:
  governance-механизма не существовало; в release-пути оставался
  непредрешённый численный допуск `TOKENIZER_CONSISTENCY_ALLOWANCE = 48`
  (внесён QF-015 после implementation без maintainer Decision), а
  thresholds.md документировал диапазон `[tokenize_count, tokenize_count+48]`.

## Реализация

- **`scripts/qualify.py`**: `TOKENIZER_CONSISTENCY_ALLOWANCE = 48` и численный
  диапазон удалены; `_assert_tokenizer_consistency` осталась fail-closed БЕЗ
  допуска: usage диагностической completion обязан быть измеренным целым > 0
  и не ниже счёта токенизатора (chat-шаблон только добавляет токены);
  `assert_threshold_governance()` — release-кампания (`--executor isolated`)
  блокируется (exit 3) до host probe и первого Worker-вызова, если revision
  thresholds.md не покрыт accepted Decision; local-dev не гейтится (диагностика,
  verdict капится non-release).
- **`scripts/threshold_governance.py`** (новый):
  - `undocumented_numeric_gates(source, documented)` — сканер
    allowance-констант (ALLOWANCE/TOLERANCE/SLACK = число) в runner,
    не покрытых thresholds.md/decisions.md;
  - `approved_revisions`/`check_revision(revision)` — revision thresholds.md
    (git hash-object, попадает в manifest) утверждён только разделом
    Decision со статусом **accepted**, содержащим строку
    «Approved thresholds revisions» (префиксное сопоставление ≥ 6 hex);
    draft/superseded ничего не утверждают.
- **`backlog/product/v3/thresholds.md`**: секция «Токенизация (QF-015)» с
  допуском `+48` УДАЛЕНА; файл — источник только утверждённых T1–T8 + ссылка
  на host contract. Новая revision:
  `3c6e52f7a0909a921a2c0b0957303264344af558`.
- **`backlog/product/v3/qualification-host-contract.md`** (новый): правила
  measurement-хоста (endpoint, модель, measured context, tokenizer,
  fingerprint, consistency без допуска) и governance-правила; численный
  допуск возможен только через Human Gate → Decision → implementation.
- **`backlog/product/v3/decisions.md`**: DR-3.0-4 (accepted) — правило
  governance + approved revision `3c6e52f7a090…` (baseline после удаления
  допуска; само удаление — предмет этого Decision, восстановление
  дореформенного состояния, не ослабление порога).

## Проверки

| # | Команда | Результат |
|---|---|---|
| 1 | Red: `pytest tests/unit/test_threshold_governance.py -q` на `c098438` | collection `ModuleNotFoundError` (механизма нет; в коде был `= 48`) |
| 2 | тот же файл после реализации | 9 passed, exit 0 |
| 3 | `pytest tests -q -p no:cacheprovider --junitxml=…` | tests=628, failures=0, errors=0, **skipped=7**, exit 0 (621 passed) |

Покрытие: константа-допуск отсутствует и сканер молчит; `+48`/«Токенизация»
отсутствуют в thresholds.md; текущая revision утверждена; мутация thresholds
(tmp-файл) не утверждена → `assert_threshold_governance` raising
`QualificationError` (governance); draft-Decision не утверждает; usage ниже
счёта/неизмеренный/булев — consistency отказ; usage ≥ счёта — проход;
fingerprint drift по-прежнему инвалидирует кампанию (тесты QF-015 зелёные).

Дерево чистое после commit; tracked evidence не перезаписывался.
