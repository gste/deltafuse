# DeltaFuse 3.0 — release qualification report

- **Статус:** `blocked-engineering`
- **Пороги:** [thresholds.md](thresholds.md) (T1–T8, absolute)
- **Runner:** [scripts/qualify.py](../../../scripts/qualify.py)
- **Обновлён:** 2026-09-12 (повторная проверка; см. [completion plan](completion-plan.md))

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

**Прогоны ещё не выполнялись.** Сначала требуется закрыть инженерные блокеры
runner из completion plan; референсный host с моделью также недоступен на машине
разработки. Данные заполняются только фактическими результатами.

## 3. Что уже проверено без модели (2026-09-12)

- Полный сьют: **370 passed, 1 skipped** (`no local PBT runner`).
- Wheel smoke: `pip wheel` → установка в чистый venv → запуск CLI и `init` на
  свежем продукте — rc 0; asset bundle с manifest едет внутри wheel.
- Оба smoke-теста (Git Bash + PowerShell) и layout validation — зелёные.
- Negative test: артефакт `schema_version` вне v3 получает blocking diagnostic
  и не конвертируется (`test_contract_v3.py`).

## 4. Критерии закрытия DF3-009

1. Три чистых прогона каждого case выполнены на референсном host.
2. Каждый отчёт прогона и медианы удовлетворяют T1–T8.
3. `verdict: pass` по всем трём cases → карточка закрывается, v3.0.0 release.
