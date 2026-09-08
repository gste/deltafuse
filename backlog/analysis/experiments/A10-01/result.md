# Результат эксперимента A10-01

- **ID карточки:** A10-01
- **Ревизия старта:** `8f05314`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `CODE-001`, `TEST-001`, `PROC-004`, `PROC-007`
- **Вердикт:** **pass** — сравнение на S02 и S05 записано. Ни одна рука не даёт сквозной `converged`. SDD не принят как улучшение: на S05 он дальше по файлам, pytest/hidden не зелёные. Prompts A09 не подкручивали.

## Ожидаемое

На одинаковых модели, raw input, oracles и бюджетах сопоставить DeltaFuse и spec → task → test/code → review: качество, intent loss, context, human time, файлы, согласования. Tiny fix и cross-capability отдельно. Дешёвый процесс, пропускающий дефекты, не считать улучшением.

## Наблюдаемое

Матрица: [sdd-vs-deltafuse.md](../../matrices/sdd-vs-deltafuse.md). SDD: [prompts/sdd.md](prompts/sdd.md), [run_sdd.py](run_sdd.py). Oracle в prompt не входил.

### S02 (tiny)

| Рука | n | Код | Hidden | LLM вызовы |
|---|---|---|---|---|
| DF A09-01a r3–r5 | 3 | TASK-001 Green | 2 passed | ~10–12 |
| SDD r1 | 1 | penalty | **2 passed** | 5 |
| SDD r2 | 1 | penalty | fail lock | 6 |
| SDD r3 | 1 | penalty | fail expiry; свои тесты pass | 5 |

DF S02 нёс калибровочные extras. SDD — нет.

### S05 (cross-capability)

| Рука | Spec оба cap | Код get_stats | Integration file | pytest |
|---|---|---|---|---|
| DF A09-03 | нет (F-010) | нет | нет | not-run |
| SDD r1–r3 | да | да | да | fail 2–3 теста |

SDD implement ~128–149 с, review prompt ~17–19k chars (ещё в бюджете шага). Catalog r1: `usage_stats` есть, `rate_policy` в `_capabilities.yaml` нет.

## Ограничения

n=3. Сравнение не ablation. Hidden S05 `slices >= 2` к SDD не применять. Warm TTFT не обобщать.

## Handoff

- **Готово A10-01:** `done` / `pass` (полнота сравнения). Дальше [A10-02](../../packets/A10-02.md) (ablation по одному механизму). Параллельно [A11-01](../../packets/A11-01.md).
- Не подкручивать A09. Skills не патчить.
- SDD не заменяет ядро: независимый hidden suite обязателен (S02 r3).
