# QF-007 — результат исполнения

- **Статус:** выполнено
- **Базовый commit:** `e599741` (QF-006)
- **Инструменты:** Python .venv 3.12.14 (uv), pytest, git 2.45.1, Windows 10.0.26200

## Реализация (`scripts/qualify.py`)

- `probe_host` возвращает provenance-структуру: каждое обязательное поле —
  `{value, provenance, method|basis, ...}` (measured: id, context,
  model_state, model_params, probe_prompt_tokens, loaded_models, tokenizer;
  declared: host, host_base_url, context_window_tokens_required,
  cloud_fallback с basis про единственный локальный endpoint и тест
  `test_no_second_transport`).
- `_probe_tokenizer(base_url)`: discovery `POST /api/v0/tokenize`;
  endpoint есть → калибровка фиксированным текстом `CALIBRATION_TEXT`
  (~1 КиБ) и `fingerprint = sha256(json(token_ids))`, value
  `host-tokenize`; endpoint отсутствует (404 / connection error) → честный
  `chars-div-4-fallback`, `fingerprint: null`; endpoint отвечает
  HTTP≠404 или мусором → блокирующий `QualificationError` (тихий fallback
  запрещён).
- `attest_manifest_model(probe)` — self-check: measured требует method,
  declared требует basis; вызывается в `main()` перед записью manifest.
- Readers обновлены (`["id"]["value"]` и т.п.); manifest["model"] =
  attested-структура; per-run report продолжает писать скалярный id.

Пример блока `model` (синтетический, из stub-пробы):
```yaml
model:
  id: {value: ornith-1.5-35b-a3b, provenance: measured, method: GET /v1/models}
  context_window_tokens: {value: 32768, provenance: measured, method: GET /api/v0/models max_context_length}
  tokenizer:
    value: host-tokenize
    provenance: measured
    method: POST /api/v0/tokenize (endpoint discovered)
    fingerprint: 6a19b0c5e9ab39f2...
  cloud_fallback:
    value: false
    provenance: declared
    basis: runner builds a single local endpoint (HOST_BASE_URL); no other
      transport exists in the runner code (test_no_second_transport); OS-level
      egress is not attested at L1
```

## Red-фаза (до реализации)

```
FAILED test_manifest_fields_carry_provenance - AttributeError: attest_manifest_model
FAILED test_tokenizer_fingerprint_recorded - KeyError: 'tokenizer'
FAILED test_tokenizer_endpoint_error_blocks_campaign
FAILED test_tokenizer_endpoint_garbage_blocks_campaign
FAILED test_tokenizer_absent_records_fallback - KeyError: 'tokenizer'
FAILED test_cloud_fallback_is_declared_not_measured - TypeError (plain dict)
```

Не-Red: `test_no_second_transport` проходил сразу (второго транспорта в коде
и не было — это и есть заявленный инвариант; тест закрепляет).

## Green-фаза

```
.venv/Scripts/python.exe -m pytest tests
430 passed, 1 skipped, 54 warnings in 248.24s   (0 failed)
```

Smoke: ps1 rc=0, sh rc=0.

## Acceptance

- [x] Manifest различает measured/declared/derived; self-check + тест.
- [x] Model id ≠ reference, context < 32768, отсутствие usage — блок
      (ранее существующие тесты); ошибка/мусор tokenizer-endpoint — блок
      (новые тесты).
- [x] Fingerprint при host-tokenize; fallback помечен методом и
      `fingerprint: null`.
- [x] `cloud_fallback` — declared с basis; тест единственности транспорта.
- [x] Полный suite 0 failed; оба smoke rc=0.
