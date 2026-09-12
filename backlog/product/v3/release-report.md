# DeltaFuse 3.0 — release qualification report

- **Статус:** `engineering-failed`
- **Пороги:** [thresholds.md](thresholds.md) (T1–T8, absolute)
- **Runner:** [scripts/qualify.py](../../../scripts/qualify.py)
- **Обновлён:** 2026-09-12 (независимая проверка №3; см.
  [qualification fix plan](qualification-fix-plan.md))

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

**Прогоны ещё не выполнялись.** Сначала требуется закрыть инженерные блокеры из
[qualification fix plan](qualification-fix-plan.md); референсный host с моделью
также недоступен на машине разработки. Данные заполняются только фактическими
результатами.

## 3. Независимая инженерная перепроверка без модели (2026-09-12)

Заявленная квалификация выполнялась на commit
`25551473ad4c07a4c5b1e2fabdd782792f7e6975`. Независимая перепроверка выполнена
на commit `c12803d` ветки `feature/2026-09-11-audit` после заявленных
исправлений:

1. Полный pytest-сьют в независимом окружении: **1 failed, 382 passed,
   1 skipped**. Failure:
   `tests/unit/test_qualify.py::test_allowed_shell_commands_still_run` — команда
   `python -m pytest --version` выбрала Python без pytest.
2. `tests/smoke-test.ps1` — rc 0.
3. `tests/smoke-test.sh` (Git Bash) — rc 0.
4. Default wheel smoke перезаписывает tracked build manifest: версия Python и
   wheel hash меняются. Изменение после проверки было откатано; тест не
   удовлетворяет требованию чистого дерева.
5. Layout validation чистого v3-продукта (sh-валидатор) — rc 0.
6. Поиск legacy runtime paths: остались только намеренные negative-фикстуры
   (`schema_version: 2` в тестах fail-closed); bench seed catalogs переведены
   на v3.

Дополнительные блокеры подтверждены прямыми probes: пустой envelope разрешает
запись `src/evil.py`; `git diff --output=leak.txt` проходит parser; T5 сообщает
`unique_files: 0` после реального чтения файла. Asset replacement остаётся
неатомарным, T8 проходит без обязательного defense evidence, а host fallback и
tokenizer provenance не измеряются полностью.

**Инженерный блокер не снят.** Исправления перечислены в
[qualification-fix-plan.md](qualification-fix-plan.md). Кампания
`scripts/qualify.py` не принимается для reference qualification до выполнения
QF-001–QF-011; отсутствие LM Studio отдельно блокирует QF-012.

## 4. Критерии закрытия DF3-009

1. Три чистых прогона каждого case выполнены на референсном host.
2. Каждый отчёт прогона и медианы удовлетворяют T1–T8.
3. `verdict: pass` по всем трём cases → карточка закрывается, v3.0.0 release.
