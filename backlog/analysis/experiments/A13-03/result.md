# A13-03 — маршруты docs/ops и Analyze (R2)

**Verdict: `partial`.** n=1, HEAD `903819a`, SUT `:1240` ornith, thinking off. Extras не патчил. Hidden не в prompt. Implement/pytest не достигли.

Рабочая гипотеза (RM-020/021/022/018/030 видны на SUT) подтверждена **только на Analyze-маршрутах**. Specify везде YAML-fail; 2 slices на S05 не появились (stock extra «ONLY SLICE-01»).

| Case | Стоп | `route` | Наблюдение vs ожидание R2 |
|---|---|---|---|
| S03 | specify fail (3) | `code` | Spec/`limiter.py` в Specify не писал (только `spec-delta.md`). `requirement_delta: none` и authentic Red **not-tested**. `analyzed` сломан битым spec-delta. |
| S08b | specify fail (3) | **`docs`** | RM-021 на routing. Specify писал live `ratelimit.md`, **не** `limiter.py` (hash seed `6a3bdd312dd7`). Гейт: якоря `#usage-examples` нет. Product pytest **not-tested**. |
| S08c | specify fail (3) | **`ops`** | RM-021 на routing. Specify не писал deploy YAML / `docs/ops/**` / spec. `blocked-on-decision` на попытке 1 без DEC. |
| S05 Analyze | coverage pass | `code` | Routing first; **1** slice; `analysis.md` нет (RM-030 ok). `check_gate(analyzed)=[]`. `schema_version` на routing не было (лишний ключ **not-tested**). ≥2 slices **fail** при текущем extra. |
| S02 Analyze | coverage pass | `code` | Claims `CR-001..006` в coverage; литеральных O1/E1 в `request.md` нет (intake уже CR-*). `call_width` не снимал Specify (Specify не вызывали). `analyzed=[]`. |

S05: два CHG-каталога (`extend-…` пустой vs `rate-limiter-usage-policy` с артефактами). Срезы/routing смотреть во втором.

Не открывал новый RM: Specify-fail — форма YAML/якоря, не vacuous `specified` и не «ослабить гейт».

## Handoff

- R2 `partial`. [A13-04](../../packets/A13-04.md) optional: Verify/S10/S11; не блокер контракта. Нужен `:1240`.
- Полный A09 11/11 не гонять. Extras SLICE-01 не патчить «чтобы было 2».
