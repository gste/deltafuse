# DeltaFuse 3.0 — release qualification report

- **Статус:** `pending-reference-runs`
- **Пороги:** [thresholds.md](thresholds.md) (T1–T8, absolute)
- **Runner:** [scripts/qualify.py](../../../scripts/qualify.py)
- **Обновлён:** 2026-09-12 (после стабилизации After Audit #2: runner реализован — V3-FIX-001/023/024; статусы строк таблицы остаются `pending` до прогонов)

## 1. Референсная конфигурация

| Параметр | Значение |
|---|---|
| Модель Worker | `ornith-1.5-35b-a3b` (локальная, 35B A3B) |
| Host | LM Studio, OpenAI-совместимый endpoint, context limit 32768 |
| Cloud/mock fallback | запрещён карточкой DF3-009 |
| Framework pin | фиксируется `scripts/qualify.py` на момент прогона |

## 2. Прогоны (по три чистых прогона на case)

Каждый прогон публикуется как disk report в `bench/runs/<campaign>/<run_id>/report.yaml`
(формат — [thresholds.md](thresholds.md)). **Все** прогоны каждого case приводятся;
выбор лучшего прогона запрещён.

| Case | Run 1 | Run 2 | Run 3 | Медиана correctness | Медиана process | Verdict |
|---|---|---|---|---|---|---|
| M01-cooldown | _pending_ | _pending_ | _pending_ | — | — | pending |
| M02-policy-stats | _pending_ | _pending_ | _pending_ | — | — | pending |
| M03-adversarial | _pending_ | _pending_ | _pending_ | — | — | pending |

**Прогоны ещё не выполнялись: референсный host с моделью недоступен на машине
разработки.** Данные строки заполняются только фактическими результатами
`scripts/qualify.py`; Fabricating results запрещён правилами программы.

## 3. Что уже проверено без модели (2026-09-12)

- Полный сьют: **336 passed, 1 skipped** — включая fail-closed тесты DF3-008
  (unknown version, legacy vocabulary), receipt-профили DF3-007 и
  unique-forward-transitions scoring (C-01 закрыт, тест перевёрнут в зелёный).
- Wheel smoke: `pip wheel` → установка в чистый venv → `deltafuse validate-config`
  на свежем продукте — rc 0; asset bundle с manifest едет внутри wheel.
- Оба smoke-теста (bash + PowerShell) и layout validation — зелёные.
- Negative test: артефакт `schema_version` вне v3 получает blocking diagnostic
  и не конвертируется (`test_contract_v3.py`).

## 4. Критерии закрытия DF3-009

1. Три чистых прогона каждого case выполнены на референсном host.
2. Каждый отчёт прогона и медианы удовлетворяют T1–T8.
3. `verdict: pass` по всем трём cases → карточка закрывается, v3.0.0 release.
