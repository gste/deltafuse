# A13-04 — неизвестные A12 на SUT (R3, optional)

**Verdict: `partial`.** n=1, SUT `:1240`. Тема: **S11 два Change / F-006**. Analog и v2-префилл не гонял.

F-006 на живой серии **не наблюдался**: оба Change остановились на Specify (YAML/якоря), merge и CHG-C skipped. Контракт RM-006 по-прежнему только unit (`stale Green`), не SUT.

| Тема | Вердикт | Почему |
|---|---|---|
| S11 CHG-B window stats | specify fail (3) | `change.yaml` deltas/slices schema; spec-delta без `---`; якоря `#req-rl-05..08` нет в live spec |
| S11 CHG-A burst_allowance | specify fail (3) | те же классы YAML; `burst_allowance` в live spec **не** зафиксирован как specified |
| S11 merge / CHG-C | not-tested | нет CHG-B Green и CHG-A Specify pass |
| Verify/Archive S02/S03 | not-tested | R1 не дошёл до Target |
| S10 interrupt | not-tested | нет времени на mid-phase restart при устойчивом Specify-fail |
| Analog live | not-tested | не эта очередь |

Новый RM не открывал: Specify-fail воспроизводит агентный YAML, не silent-pass F-006.

## Handoff

Очередь A13 закрыта. Вердикт очереди по плану: **`partial`** (R0 зелёный; R1 n=1 без S04 Human Gate; S05 не vacuous specified). Следующая задача анализа: нет.
