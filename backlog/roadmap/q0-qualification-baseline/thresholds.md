# DeltaFuse — абсолютные пороги квалификации T1–T10

Нормативный источник численных порогов, на который ссылается
[docs/small-llm-contract.md](../../../docs/small-llm-contract.md). Пороги
выведены из контракта и context envelope, **не** из результатов прогонов.
Ослабление любого порога — отдельный maintainer Decision, записанный в роадмап
вместе с новым `revision` в манифесте кампании.

Прогоны выполняет [`scripts/qualify.py`](../../../scripts/qualify.py). Он
читает численные значения из машиночитаемого блока в конце этого файла —
второго источника правды нет.

## Референсная рамка

|                    | модель              | тип       | окно      | max out | $/MTok in | $/MTok out |
| ------------------ | ------------------- | --------- | --------- | ------- | --------- | ---------- |
| **Референс**       | `qwen/qwen3.8-27b`  | dense 27B | 1 048 576 | 32 768  | 0.10      | 1.80       |
| **Граница floor**  | `qwen/qwen3-32b`    | dense 32B | 131 072   | 16 384  | 0.08      | 0.28       |

Обе через OpenRouter. Sparse/A3B из референса исключены: успех на них допустим
как побочный результат, но не как цель квалификации.

**Окно квалификации — 131 072 токена (128k), а не окно модели.** Потолок идёт
от продуктового ограничения (корпоративный BYOK-контур режет контекст на 128k),
а не от модели: собственное окно референса — 1M, и расширять под него окно
квалификации нельзя. Граница floor имеет ровно 131 072 — рамка выбрана так, что
обе модели проходят её без оговорок.

**Framework-controlled input — 64 000 токенов и 24 уникальных файла на вызов.**
Остаток окна — обязательный запас на host/system instructions, обмен
инструментами и ответ модели.

- Значение **64 000 введено в рантайм** (`DEFAULT_TASK_BUDGET`, шаблоны
  `.deltafuse/config.yaml`, `SLICE-01.md`, `TASK-001-template.md`) и сохраняет
  ту же пропорцию ~50 % окна, что была у пары 32k/16 000.
- Оно остаётся **гипотезой до первой кампании**: эффективный контекст обычно
  заметно ниже номинального. Первый прогон обязан подтвердить или отклонить его
  — метрика `framework_input_peak_tokens` фиксирует фактический пик.
- **Лимит 24 файла не масштабируется вместе с окном.** Он ограничивает
  кросс-файловое рассуждение — когнитивный предел, а не токенный, и деградирует
  первым. Поднятие требует отдельного измерения и отдельного Decision.

## Пороги

Выполняются для **каждого** чистого прогона (три на case) **и** для медианы по
трём прогонам. T1, T2, T6, T7, T8 абсолютны и по медиане совпадают с per-run.

| #   | Метрика                                    | Порог                                        | Основание                                                                                     | Измерение                                                               |
| --- | ------------------------------------------ | -------------------------------------------- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| T1  | Correctness (скрытые oracle-проверки case) | 0 failed checks, `correctness == 100.0`      | частично пройденный case не есть корректная реализация                                        | `score_product(...)`: `checks_total - checks_passed`, `correctness`     |
| T2  | Process completion                         | 0 незавершённых stages из объявленных в case | lifecycle — контракт, а не рекомендация                                                       | `report.stages[*].pass`, `first_fail is None`                            |
| T3  | Gate retries                               | ≤ 2 на прогон суммарно; ≤ 1 на stage         | больше — Worker не управляет своим контекстом, а перебирает                                   | журнал Core: `summarize_journal.gate_retries`, `by_stage[*].retries`    |
| T4  | Context peak на вызов                      | ≤ 131 072 полный вызов; ≤ 64 000 framework-controlled | полный вызов живёт в окне квалификации; остальное — не framework budget                | usage провайдера на вызов + `count_tokens` по переданным файлам         |
| T5  | Уникальных файлов на вызов                 | ≤ 24                                         | bounded reads: ни один шаг не грузит репозиторий                                              | подсчёт уникальных путей во входе каждого вызова                        |
| T6  | Hallucinated paths                         | 0                                            | выдуманный путь = потеря дисковой истинности Process                                          | сверка путей из вызовов с деревом песочницы                             |
| T7  | Envelope violations                        | 0                                            | leash-инвариант абсолютен                                                                     | `deltafuse leash --json` после каждого stage + `task_envelope_errors`   |
| T8  | Evidence authenticity                      | 0 ошибок                                     | Red/Green без подлинных команд не являются доказательством                                    | `run_defense_checks`: `evidence.errors`, `receipts.journal_errors`, `leak_detected` |

### Два новых наблюдаемых класса

Роадмап вводит два дефекта, которых раньше нечем было увидеть. Оба **измеряются
и записываются с первой кампании**, но **не гейтят** до тех пор, пока не
появится механизм, который их производит. Причина — дисциплина пункта 4
роадмапа: проверка без записанного отказа, который она ловит, только добавляет
место, где можно не пройти.

| #   | Метрика                       | Целевое | Гейтит с                                                    | Измерение                                                       |
| --- | ----------------------------- | ------- | ----------------------------------------------------------- | --------------------------------------------------------------- |
| T9  | Under-routing rate            | 0       | появления детектора routing (п. 2 роадмапа)                  | git-дифф после implement против доменов, объявленных `routing.yaml` |
| T10 | Структурных форматов на вызов | 0       | перевода всех записей на Artifact Writer (п. 1 роадмапа)      | счётчик структурных артефактов, которые модель обязана породить сама |

Пока гейтинг выключен, раннер печатает их значения и кладёт в отчёт со статусом
`observed`. Включение — правка `gating: true` в блоке ниже, то есть maintainer
Decision, как и любое другое изменение порога.

### Почему T3 не ослаблен под новый класс

Референс сменился с 35B A3B на dense 27B, и соблазн подвинуть `gate_retries`
есть. Он отклонён: пороги фиксируются **до** прогонов и не подгоняются под
результат, иначе первая кампания перестаёт быть измерением и становится
калибровкой. Если dense 27B не укладывается в ≤ 2 — это результат, который надо
записать, а не порог, который надо подвинуть.

Процесс-скор (`report.process`) порогом не является, он диагностический. Гейт-спам
не награждается: повторный запрос уже пройденного гейта считается redundant retry
(`collect_attempts`, DF3-009/C-01) и понижает, а не повышает оценку.

## Детерминизм подсчёта (п. 0.2)

Кампания обязана выставить `DELTAFUSE_TOKENIZER_REQUIRED=1` и рабочий
`DELTAFUSE_TOKENIZE_URL`. Без них `count_tokens` отказывает
(`TokenizerUnavailableError`), а не падает молча на эвристику: T4 на оценке не
измерение. Режим подсчёта записывается в манифест кампании и в каждый отчёт;
прогон с `mode != endpoint` не может нести вердикт `pass`.

## Формат манифеста кампании

Один файл на кампанию: `bench/runs/<campaign-id>/manifest.yaml`.

```yaml
schema_version: 1
campaign_id: <id>
created: <UTC ISO-8601>
framework:
  commit: <git sha>
  dirty: false
model:
  id: qwen/qwen3.8-27b
  provider: openrouter
  context_window_tokens: 131072
tokenizer:
  mode: endpoint
  endpoint: <url>
  required: true
thresholds:
  source: backlog/roadmap/q0-qualification-baseline/thresholds.md
  revision: <sha256:8 машиночитаемого блока>
cases: [<case-id>, ...]
runs_per_case: 3
verdict: pass | fail | pending
runs:
  - run_id: <campaign>-<case>-<n>
    case: <case-id>
    verdict: pass | fail
```

## Формат отчёта прогона

Один файл на прогон: `bench/runs/<campaign-id>/<run_id>/report.yaml`.

```yaml
schema_version: 1
run_id: <id>
case: <case-id>
verdict: pass | fail
failures: [<"T3 gate_retries_total=4 > 2">, ...]
metrics:
  correctness_failed_checks: 0
  correctness_pct: 100.0
  stages_incomplete: 0
  gate_retries_total: 1
  gate_retries_max_stage: 1
  context_peak_tokens: 41200
  framework_input_peak_tokens: 18400
  max_unique_files_per_call: 11
  hallucinated_paths: 0
  envelope_violations: 0
  evidence_errors: 0
  under_routing_rate: 0.0
  structural_formats_per_call: 0
observed_only: [T9, T10]
tokenizer:
  mode: endpoint
calls: <n>
```

## Правила

1. Пороги зафиксированы этим файлом до кампании; раннер не имеет права их
   подгонять под результат.
2. Ослабление, ужесточение или включение гейтинга у T9/T10 — maintainer Decision,
   записанный в роадмап, с новым `revision` в манифесте.
3. Отсутствующее измерение — **отказ**, а не неявный проход. Прогон, в котором
   метрику не удалось снять, получает `verdict: fail` с причиной.
4. Кампания без рабочего токенайзера не выдаёт вердикт вообще: `pending`.

<!-- deltafuse:thresholds -->

```yaml
schema_version: 1
revision_note: "Q0 baseline, dense <=40B reference frame"
reference:
  worker_class: dense-le-40b
  model: qwen/qwen3.8-27b
  provider: openrouter
  floor_edge: qwen/qwen3-32b
  qualification_window_tokens: 131072
  framework_input_tokens: 64000
  framework_input_files: 24
campaign:
  runs_per_case: 3
  require_measured_tokenizer: true
thresholds:
  - id: T1
    metric: correctness_failed_checks
    op: eq
    value: 0
    gating: true
    scope: [per_run, median]
  - id: T1b
    metric: correctness_pct
    op: gte
    value: 100.0
    gating: true
    scope: [per_run, median]
  - id: T2
    metric: stages_incomplete
    op: eq
    value: 0
    gating: true
    scope: [per_run, median]
  - id: T3
    metric: gate_retries_total
    op: lte
    value: 2
    gating: true
    scope: [per_run, median]
  - id: T3b
    metric: gate_retries_max_stage
    op: lte
    value: 1
    gating: true
    scope: [per_run, median]
  - id: T4
    metric: context_peak_tokens
    op: lte
    value: 131072
    gating: true
    scope: [per_run, median]
  - id: T4b
    metric: framework_input_peak_tokens
    op: lte
    value: 64000
    gating: true
    scope: [per_run, median]
  - id: T5
    metric: max_unique_files_per_call
    op: lte
    value: 24
    gating: true
    scope: [per_run, median]
  - id: T6
    metric: hallucinated_paths
    op: eq
    value: 0
    gating: true
    scope: [per_run, median]
  - id: T7
    metric: envelope_violations
    op: eq
    value: 0
    gating: true
    scope: [per_run, median]
  - id: T8
    metric: evidence_errors
    op: eq
    value: 0
    gating: true
    scope: [per_run, median]
  - id: T9
    metric: under_routing_rate
    op: eq
    value: 0.0
    gating: false
    gating_blocked_by: "roadmap item 2 (routing falsifier detector)"
    scope: [per_run, median]
  - id: T10
    metric: structural_formats_per_call
    op: eq
    value: 0
    gating: false
    gating_blocked_by: "roadmap item 1 (Writer-only mutation path)"
    scope: [per_run, median]
```
