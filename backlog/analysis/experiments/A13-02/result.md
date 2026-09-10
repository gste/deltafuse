# A13-02 — P0 holdout на ornith (R1)

**Verdict: `partial`.** n=1, HEAD `24093c8`, SUT `ornith-1.5-35b-a3b` на `:1240` (`--reasoning off`, `--cpu-moe`). Studio `:1234` не использовался. Skills с текущей ветки. Extras «только SLICE-01» не патчил. Hidden не в prompt.

Рабочая гипотеза (новые гейты ловят A09-пропуски) **частично** подтверждена: S05/S01 больше не дают vacuous `specified`. S02 Target (F-009) и S04 Analyze (Human Gate) **не дошли** из‑за YAML intake/specify.

| Case | Фаза-стоп | `specified` | Live oracle-файлы | Критерий R1 |
|---|---|---|---|---|
| S05 | specify fail (3) | fail | нет `usage_stats.md` / `rate_policy.md`; есть seed `ratelimit.md` | **pass** — не vacuous specified; два slice-файла не заменили live spec (только `SLICE-01`) |
| S01 | specify fail (3) | fail | нет `security/ratelimit.md` | **pass** — пустой продукт не `specified` |
| S02 | specify fail (3) | fail | seed `ratelimit.md` есть | **not-tested** F-009 (Target не запускался) |
| S04 | intake fail (3) | нет spec-delta; status `normalized` | seed `ratelimit.md`; DEC только шаблон | **partial** — не auto-accept Specify/Decision; `blocked-on-decision` на Analyze не измерен |

S05 catalog записал `policies.rate_policy` на существующий `ratelimit.md`; гейт отверг extra key. Независимый `check_gate(specified)` после прогона: ошибки, не `[]`.

S04 `change.yaml: analysis: null` → intake fail. Specify не вызывался. Это не 3/3 Human Gate A09-01c, но и не auto-accept DEC.

## Handoff

- F-010 на SUT: vacuous `specified` **не** повторился (S05/S01). A13-03 **можно** стартовать при живом `:1240`.
- F-009 / S02 Target и полный S04 Analyze — пробел n=1; не открывать новый RM. Не гонять A09 11/11.
- Сервер `:1240` оставлял запущенным после карточки (локальный процесс).
