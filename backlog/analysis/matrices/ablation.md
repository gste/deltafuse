# Ablation механизмов DeltaFuse (A10-02)

Дата: 2026-09-08. Копия экспериментальная (A09 harness + env), **не** патч `process/skills` / `fsm.py`. Prompts A09 на диске не меняли.

База: S05 holdout A09-03 (1 slice extra ON). Tiny: S02 A09-01 / A10-01. Human: S04 A09-01c.

Решения: **сохранить** / **адаптировать** / **исследовать** / **не переносить** / **упростить**. Снижение цены ценой пропуска дефекта не принято.

| ID | Механизм | Case | Изолят | Предотвращённый дефект | Цена | Решение |
|---|---|---|---|---|---|---|
| AB-01 | Typed spec-delta + гейт `specified` | S05 | A09-03 r2: гейт зелёный без `usage_stats.md`/`rate_policy.md` (F-010). A10-02 r2-ablate: снова `gate ok`, oracle-пути всё ещё нет | Не предотвращает отсутствие live spec | 3 retry YAML; schema `added:` как путь | **исследовать** в A12 (усилить гейт). Отключать гейт **не** улучшение |
| AB-02 | Frozen extra «только SLICE-01» | S05 | A09-03: 0/3 парных slices. A10-02 r2: extra OFF → SLICE-01+SLICE-02 за 2 попытки (prompt заменён в рантайме) | Даёт 2 среза (оракул hidden ≥2). **Не** даёт oracle spec files | 1 строка extra; без неё 2 файла | **упростить extra** в A12 (не skill). Routing.yaml оставить |
| AB-03 | `routing.yaml` (capability routing) | S05/S07 | Все DF Analyze пишут routing. SDD A10-01 без routing всё же написал два spec | Навигация claims→capability; S07 всё равно упал позже | 1 RTT ~20–43 с | **сохранить** первым шагом Analyze (Q-001). Не считать достаточным для multi-cap |
| AB-04 | `analysis.md` (summary) | S02/S05 | A09: файла нет; `analyzed` проходит на routing+slices+coverage | Не измерен отдельный дефект от отсутствия summary | skill просит, гейт не требует | **упростить** skill (optional). Новый LLM **not-tested** |
| AB-05 | Дублируемые metadata (`schema_version`) | S02 | A09-01 r2: routing fail extra key; harness strip → pass | Без strip routing не закрывается | 0–3 retry | **адаптировать** клиент strip; не раздувать schema. Новый LLM **not-tested** |
| AB-06 | Human Decision gate | S04 | A09-01c: 3/3 `blocked-on-decision`, без Specify. S12: агент не auto-accept | Ложный specified на вилке (SPEC-002) | DEC файл + стоп | **сохранить**. OFF **not-tested**: отключение = сам дефект, не экономия |

## Новый прогон AB-02 (S05 r2-ablate-slices)

- Intake/routing/coverage pass; slices: 2 файла, `monitoring.usage_stats` / `security.rate_policy`.
- Specify attempt 3 `gate ok`; live spec только `ratelimit.md` (REQ-RL-05/07); catalog `usage_stats`/`rate_policy` → тот же файл. Oracle `usage_stats.md` + `rate_policy.md`: нет.
- r1-ablate intake fail (битый `change.yaml`) — не фактор extra.

n=1 на ablation. Не статистика.

## not-tested

- n=3 на AB-02.
- Specify extra OFF (typed delta) отдельным прогоном: F-010 уже показывает слабость гейта.
- Human gate OFF.
- Ablation `coverage.yaml` целиком.
- Другие модели.
