# QF-007 — проверяемый host attestation

- **Приоритет:** P1
- **Зависимости:** QF-006 (tokenizer-probe из T4 уже существует)
- **Commit:** `qualify: attest reference host`
- **Исходный дефект:** [qualification-fix-plan.md, QF-007](../../qualification-fix-plan.md)
- **Код на момент написания:** commit `bb02820` + QF-001…QF-006

Исполнитель: читай [README.md](../README.md); конвенция «Provenance полей
manifest» вводится этим пакетом.

## 1. Дефект

`probe_host` в `scripts/qualify.py` уже измеряет context limit, state,
model params и diagnostic usage (V3-FIX-024), но:

1. `cloud_fallback: False` записывается константой в блок `model` без
   пометки, что это заявление раннера, а не измерение:

```python
# scripts/qualify.py:210 (bb02820)
"cloud_fallback": False,  # runner construction: single local endpoint only
```

2. Tokenizer identity не фиксируется: какой токенизатор применялся к
   T4-метрикам (endpoint? оценка?) и его поведение — неизвестно.
3. Manifest не различает измеренные (`measured`), заявленные (`declared`)
   и выведенные (`derived`) поля — читатель не может отличить факт от
   инварианта конструкции.

## 2. Нормативное поведение

1. **Provenance-метки.** Блок `model` manifest'а превращается в
   структуру, где каждое обязательное поле несет источник:

   ```yaml
   model:
     id: {value: ornith-1.5-35b-a3b, provenance: measured, method: GET /v1/models}
     context_window_tokens:
       value: 32768
       provenance: measured
       method: GET /api/v0/models max_context_length
     model_state: {value: loaded, provenance: measured, ...}
     model_params: {value: {...}, provenance: measured, method: GET /api/v0/models}
     probe_prompt_tokens: {value: 7, provenance: measured, method: diagnostic completion usage}
     tokenizer:
       value: host-tokenize | chars-div-4-fallback
       provenance: measured
       method: POST /api/v0/tokenize (endpoint discovered) | documented invariant
       fingerprint: <sha256 от токенов калибровочного текста> | null
     cloud_fallback:
       value: false
       provenance: declared
       basis: >
         раннер строит единственный локальный endpoint HOST_BASE_URL;
         другого транспорта в коде нет (проверяется тестом
         test_no_second_transport); OS-уровень не аттестуется
   ```

2. **Tokenizer fingerprint.** При обнаружении endpoint токенизации (QF-006
   probe) раннер токенизирует фиксированный калибровочный текст
   (константа в qualify.py, UTF-8, ~1 КиБ, стаб на всех платформах) и
   записывает `sha256(token_ids)`. Изменение модели/токенизатора host'а
   между кампаниями видно по fingerprint. При fallback — `fingerprint:
   null` + method `chars-div-4-fallback` (честно обозначенный
   документированный инвариант, разрешённый планом QF-007).
3. **cloud_fallback как declared invariant.** Отсутствие fallback'а
   доказывается конструкцией кода, а не измерением: тест сканирует
   `scripts/qualify.py` (+ модули раннера) на отсутствие других
   URL/transport констант и внешних HTTP-вызовов, кроме `HOST_BASE_URL`
   через `_get_json`/`_post_json`/`_http_json`. Manifest публикует это как
   `provenance: declared` с `basis`; никакая внешняя проверка не
   заявляется.
4. **Fail-closed условия кампании** (каждое — отдельный блокирующий
   QualificationError, уже частично есть):
   - model id ≠ reference → блок (есть);
   - measured context < 32768 → блок (есть);
   - diagnostic completion без валидного usage → блок (есть);
   - tokenizer endpoint найден, но отвечает ошибкой/мусором → блок
     (нельзя молча упасть в fallback);
   - обязательное поле manifest без provenance-метки → блок
     (self-check перед записью manifest).

## 3. План работ

### Шаг 1 — Red-тесты (`tests/unit/test_qualify.py`)

- `test_manifest_fields_carry_provenance` — probe с полным stub: каждый
  ключ из обязательного набора имеет `value`+`provenance`(+`method`/
  `basis`); отсутствие любой метки → ошибка self-check.
- `test_tokenizer_fingerprint_recorded` — stub tokenize-endpoint возвращает
  детерминированные token ids → fingerprint = sha256 этих ids; method =
  host-tokenize.
- `test_tokenizer_endpoint_error_blocks_campaign` — endpoint отвечает 500
  → QualificationError (нет тихого fallback).
- `test_tokenizer_absent_records_fallback` — endpoint'а нет →
  `chars-div-4-fallback`, `fingerprint: null`, без ошибки.
- `test_no_second_transport` — статический анализ модулей раннера: HTTP/
  URL-константы только через единый base URL (греп-подобный тест по AST/
  исходнику; исключения — docstring/tests).
- `test_cloud_fallback_is_declared_not_measured` — в результате probe
  `cloud_fallback.provenance == "declared"` и `basis` непуст.
- Обновить `test_probe_host_diagnostic_completion` под новую структуру
  (вложенные value/provenance).

### Шаг 2 — Реализация

1. `probe_host` возвращает структуру по п.2.1 (обратная совместимость
   тестов не нужна — тесты раннера обновляются в этом же пакете).
2. `_probe_tokenizer(base_url) -> dict` — discovery + калибровка (п.2.2),
   вызывается из `probe_host`.
3. `attest_manifest_model(probe) -> None` — self-check provenance-меток
   (п.2.1 последний пункт); вызывается перед первой записью manifest.
4. `run_case`/`main`: проброс новой структуры в manifest
   (`manifest["model"]`); readers (`print(f"host probe ok: ...")`)
   обновить на `["id"]["value"]` и т.п.
5. Тест `test_no_second_transport` (п.2.3) — в tests, не в runtime.

### Шаг 3 — Регрессия

- Полный suite + smoke; проверить, что `test_live_http_probe` и probe-
  тесты обновлены согласованно.

## 4. Границы и запреты

- Не пытаться «измерить» отсутствие cloud fallback сетевыми пробами —
  это заявленный инвариант; честная метка `declared` и есть исправление
  («непроверяемое обязательное свойство не публикуется как факт»).
- Не менять HOST_BASE_URL/REFERENCE_MODEL_ID (это контракты DF3-009).
- Формат manifest финализирует QF-008 (schema): здесь — структура полей
  provenance, там — валидация файлов.

## 5. Acceptance

- [ ] Manifest различает measured/declared/derived; каждое обязательное
      поле помечено (self-check + тест).
- [ ] Mismatch model/context/tokenizer, отсутствие usage, ошибка
      tokenizer-endpoint — каждый отдельно блокируют кампанию (тесты).
- [ ] Tokenizer identity/fingerprint записывается при host-tokenize;
      fallback помечен методом и `fingerprint: null`.
- [ ] `cloud_fallback` — declared с basis; тест единственности транспорта.
- [ ] Полный suite + smoke зелёные.

## 6. Evidence для RESULT.md

1. Red-вывод новых тестов.
2. Green suite + smoke.
3. Пример блока `model` из синтетического manifest (YAML).

## 7. Commit

Один commit: `qualify: attest reference host`.
Состав: `scripts/qualify.py`, `tests/unit/test_qualify.py`, `RESULT.md`.
