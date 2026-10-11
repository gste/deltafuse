# q6: у вердикта Verify `spec-gap` нет пути назад — Change застревает

**Состояние: сделано 2026-10-11 (вариант 1, решение владельца), ветка `fix/implemented-gate-covers-red`.** `spec-gap` возвращает Change на Analyze, а не на Specify: в ref-m04-365-2 недостающая строка лежала в файле спецификации, который не называл ни один слайс, а границы слайсов пишет Analyze. Остальные пробелы останавливают Change с прямым «пути назад пока нет». Было: наблюдение, к разбору. Записано 2026-10-09 по Change на J03 после Fuse-Back, задевающему 30
характеризующих тестов (`fuseback/docs/planning/E2E-CHANGE-J03.md`, раздел «Change на многих тестах»).
DeltaFuse `578ffed` + `caf014a`.

## Что произошло

`CHG-002-violation-code-prefix`: сообщение `ContractViolation` начинается с кода ошибки. Implement обновил код и все
30 характеризующих тестов (regression зелёный), но Specify изменил только 21 наблюдаемое требование из 30: девять
записаны в другой формулировке, и Worker их пропустил. Живая спецификация противоречит коду.

Verify это увидел и записал `- Outcome: spec-gap`. Дальше:

```
advance --gate converged -> "verification.md records the gap 'spec-gap' ... fix what the gap names, then write the
                             verification again"
state --change --status verifying  -> "Change status 'verifying' is Core-gated; use deltafuse advance"
state --change --status analyzing  -> "Change status 'analyzing' is Core-gated; use deltafuse advance"
advance --gate analyzed  -> "cannot apply gate 'analyzed' from status 'implemented'"
advance --gate specified -> "change.yaml status must be 'specified' or 'specification-proposed' (got 'implemented')"
```

Исправить пробел в Verify нельзя: контракт фазы не пускает запись в `docs/spec/**`, leash (`enforce`) отвергает
коммит. `fsm.ALLOWED_CHANGE_TRANSITIONS` разрешает `verifying -> analyzing`, но ни одна команда этот переход не
применяет. Change не может ни сойтись, ни вернуться — остаётся в `implemented`.

## Почему важно

Навык verify прямо требует: «For a gap, stop; do not repair it silently». Без маршрута назад честная остановка
превращается в тупик, и у Worker'а остаётся только обходить leash.

## Варианты (решение владельца)

1. `deltafuse decide <change> --gap <verdict> --status reopened --note ...` (Human Gate): человек возвращает Change
   на шаг, который чинит пробел (`spec-gap` -> Specify, `tasks-missing`/`test-gap` -> Decompose/Declare), с
   сохранением доказательств как при `--task ... reopened`.
2. `advance --gate analyzed` из `implemented`/`verifying` при записанном gap-вердикте (переход уже в таблице).
3. Минимум — сообщение `converged` называет, как выйти из gap, а не только «fix what the gap names».

Наблюдение для Worker'а (не DeltaFuse): у каждого требования Fuse-Back есть строка `Test: <test>`; связь «тест →
требование» нашла бы все 30, а не 21. Это стоит упомянуть в навыке specify для модулей `observed`.
