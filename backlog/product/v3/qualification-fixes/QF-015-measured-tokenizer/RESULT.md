# QF-015 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `1057463` (QF-014)
- **Red evidence:** `tests/unit/test_qualify_tokenizer.py` — до реализации
  падали: absent/404/timeout/conn не блокировали (fallback возвращал
  `chars-div-4-fallback` с provenance `measured`), оценки не проходили T4,
  `tokenizer_fingerprint_matches` не существовал, consistency-проверки не
  было; обновлён legacy-тест `test_tokenizer_absent_records_fallback` →
  `test_tokenizer_absent_blocks_campaign`.

## Реализация

- **Состояния измерения**: `measured` (`host-tokenize`),
  `estimated-nonrelease` (только local-dev диагностика, `chars // 4`),
  `unavailable`, `error`. `_probe_tokenizer` полностью fail-closed: 404 /
  connection error / timeout / garbage / отрицательный или булев счёт
  токенов → `QualificationError` → кампания `PENDING` (exit 2) до первого
  Worker-вызова. `chars-div-4-fallback` удалён.
- **drive_worker**: framework tokens = host-tokenize (measured) либо
  `estimated-nonrelease` (значение `chars // 4` сохранено только как
  диагностика); агрегат в `_final_metrics` отражает новые методы
  (`estimated-nonrelease`/`unavailable`/`mixed`).
- **apply_thresholds (T4)**: `framework_input_tokens_method != "host-tokenize"`
  → fail «release requires a measured host tokenizer». Ни один report с
  не-measured provenance не получает pass.
- **Fingerprint**: sha256 token id калибровочного текста; в конце кампании
  повторный probe — расхождение (`tokenizer_fingerprint_match: false`)
  делает verdict `fail`; недоступность endpoint при перепроверке — тоже fail.
- **Consistency**: `_assert_tokenizer_consistency` — `usage.prompt_tokens`
  completion на `CALIBRATION_TEXT` обязан лежать в
  `[tokenize_count, tokenize_count + 48]` (допуск на chat-шаблон,
  `TOKENIZER_CONSISTENCY_ALLOWANCE`, задокументирован в thresholds.md §
  «Токенизация (QF-015)»).
- thresholds.md дополнен разделом «Токенизация (QF-015)».

## Проверки

- Негативная матрица: absent/404/timeout/conn, garbage, `{"tokens": -3}`,
  `{"tokens": True}`, `{"tokens": "many"}` — все блокируют.
- Методы `chars-div-4`/`estimated-nonrelease`/`unavailable`/`mixed`/None не
  проходят T4; `host-tokenize` — проходит.
- Drift fingerprint инвалидирует кампанию; NaN/boolean отклонены.
- Регрессия: 128 qualification-тестов зелёные.
