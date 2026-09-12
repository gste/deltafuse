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

## 3. Инженерная квалификация без модели (2026-09-12, completion plan шаг 8)

Выполнено на чистом commit `25551473ad4c07a4c5b1e2fabdd782792f7e6975`
(ветка `feature/2026-09-11-audit`), platform `win32 / Python 3.14`:

1. Полный pytest-сьют: **~384 passed, 1 skipped** (`no local PBT runner` —
   Hypothesis не установлен, skip обоснован в тесте).
2. `tests/smoke-test.ps1` — rc 0.
3. `tests/smoke-test.sh` (Git Bash) — rc 0.
4. Wheel smoke: `pip wheel` → установка в чистый venv → CLI `--help`, `init`,
   `validate-config` без checkout — rc 0; durable build manifest в
   `bench/builds/`; drift bundle = явный fail, дерево тест не чинит.
5. Layout validation чистого v3-продукта (sh-валидатор) — rc 0.
6. Поиск legacy runtime paths: остались только намеренные negative-фикстуры
   (`schema_version: 2` в тестах fail-closed); bench seed catalogs переведены
   на v3.

Исключения/skips: один — отсутствие локального PBT runner'а; блокеров нет.

**Инженерный блокер снят:** шаги 1–7 completion plan выполнены и закрыты
тестами; кампания `scripts/qualify.py` ожидает только референсный host
(шаг 9).

## 4. Критерии закрытия DF3-009

1. Три чистых прогона каждого case выполнены на референсном host.
2. Каждый отчёт прогона и медианы удовлетворяют T1–T8.
3. `verdict: pass` по всем трём cases → карточка закрывается, v3.0.0 release.
