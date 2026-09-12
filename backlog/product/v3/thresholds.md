# DeltaFuse 3.0 — absolute release thresholds и run manifest

Абсолютные численные пороги качества v3, зафиксированные до implementation-коммитов.
Их использует DF3-009 (qualification). Пороги выведены из Small-LLM Quality
Contract ([deltafuse-3](../deltafuse-3.md)) и context envelope, а не из результатов
прогонов предыдущей версии. Ослабление любого порога — отдельный maintainer Decision
с записью в [decisions.md](decisions.md).

## Зафиксированная рамка

- Референсный класс Worker: локальная LLM 35B A3B (`ornith-1.5-35b-a3b`, LM Studio).
  Более крупная или cloud LLM не является скрытой зависимостью release cases.
- Полный вызов Worker помещается в context window **32k токенов** (qualification window).
- Framework-controlled input по умолчанию: **≤ 16k токенов и ≤ 24 уникальных файлов**
  на вызов; остаток окна — обязательный запас для host/system instructions,
  tool exchange и ответа модели.

## Absolute release thresholds

Выполняются для **каждого** из трёх чистых v3-прогонов каждого release case
(не только медианы) и для медианы по трём прогонам.

| # | Метрика | Absolute threshold | Основание | Измерение |
|---|---|---|---|---|
| T1 | Correctness (скрытые oracle-проверки case) | 100% passed checks; допустимо 0 failures | процесс — закон: частично пройденный case не есть корректная реализация | `report.correctness.failed == 0` per stage pack DF3-009 |
| T2 | Process completion | все 7 lifecycle stages completed; 0 этапов skipped/aborted | lifecycle является контрактом, а не рекомендацией | `report.stages[*].status == "completed"` |
| T3 | Gate retries (failed check-gate cycles) | ≤ 2 на прогон суммарно; ≤ 1 на stage | больше — Worker не управляет своим контекстом, а перебирает | journal `check-gate` failed cycles (`collect_attempts.retries.check_gate`) |
| T4 | Context peak (вход Worker-вызова) | ≤ 32768 токенов на любой вызов; framework-controlled часть ≤ 16000 токенов | полный вызов живёт в 32k; остальное — не framework budget | токенизация лога каждого вызова в run manifest |
| T5 | Files loaded (уникальные файлы на вызов) | ≤ 24 | decision 2 плана: bounded reads, никакой шаг не грузит репозиторий | подсчёт уникальных путей в input каждого вызова |
| T6 | Hallucinated paths (запись/чтение несуществующих путей) | 0 | выдуманный путь = потеря дисковой истинности Process | сверка envelope/journal путей с деревом на диске |
| T7 | Envelope violations | 0 | leash-инвариант абсолютен | `leash` check по завершении каждого stage + CI |
| T8 | Evidence authenticity | 100% evidence stamps authentic; 0 синтетических команд | Red/Green без подлинных команд не являются доказательством | `evidence` errors == 0; journal `evidence` failed == 0 |

Процесс-скор не порог; он диагностический. Threshold не награждает gate spam
(C-01): повторные запросы уже пройденного гейта не считаются forward-переходами.

## Run manifest (единый формат для DF3-009)

Один файл на qualification-кампанию: `bench/runs/<campaign-id>/manifest.yaml`.

```yaml
schema_version: 1            # v3 run manifest schema
campaign_id: <id>
created: <UTC ISO-8601>
framework:
  commit: <git sha>
  lock_hash: <framework content hash>
model:
  id: ornith-1.5-35b-a3b
  host: lm-studio
  context_window_tokens: 32768
thresholds:
  source: backlog/product/v3/thresholds.md
  revision: <short sha of this file>
cases: [case-id, ...]        # release cases; runs/ рядом
runs:
  - run_id: <campaign>-<case>-<n>   # три чистых прогона на case
    case: <case-id>
```

## Per-run disk report (формат для DF3-009)

Один файл на прогон: `bench/runs/<campaign-id>/<run_id>/report.yaml`.

```yaml
schema_version: 1            # v3 per-run report schema
run_id: <id>
case: <case-id>
verdict: pass | fail         # против thresholds T1..T8, не против прошлых прогонов
stages:                      # по каждому lifecycle stage
  - stage: implement
    status: completed
    checks: {passed: 3, failed: 0}
    gate_retries: 0
calls:                       # по каждому Worker-вызову
  - input_tokens: 9120
    framework_input_tokens: 6400
    unique_files: 11
    hallucinated_paths: 0
    envelope_violations: 0
totals:
  correctness: {passed: 12, failed: 0}
  gate_retries: 1
  context_peak_tokens: 14000
  max_unique_files: 18
  hallucinated_paths: 0
  envelope_violations: 0
  evidence_authentic: true
```

## Правила

1. Пороги зафиксированы этим файлом до implementation-коммитов; DF3-009 не имеет
   права подгонять их под результаты qualification runs.
2. Ослабление (или ужесточение) любого порога — maintainer Decision, приложенный
   к [decisions.md](decisions.md), с новым `revision` в manifest.
3. Карточка не запускает исторические сравнительные прогоны; всё здесь относится
   только к v3.
