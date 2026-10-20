# q6: Red записывает в `changed_paths` незакоммиченную правку спецификации

**Состояние: наблюдение, к разбору.** Записано 2026-10-08 по сквозному Change на выходе Fuse-Back
(`fuseback/docs/planning/E2E-CHANGE-J03.md`, прогон `shopkit`). Меньше и независимо от
[CHANGE-WRITE-PATHS](CHANGE-WRITE-PATHS.md).

## Что произошло

Specify изменил `docs/spec/shared/general_utilities.md`; правка не была закоммичена. Declare записал Red:
`deltafuse evidence … --phase red -- python -m pytest tests/test_is_blank.py -q` — `Evidence is authentic`,
но в `changed_paths` попали и тест, и файл спецификации. Затем:

```
advance failed: gate 'declaring' failed: Gate declaring red changed_paths of TASK-001.yaml:
'docs/spec/shared/general_utilities.md' is outside the phase contract (Red writes tests, ...)
```

Исправить своими силами Worker не может: `state --task … --status pending` из `declared` запрещён, а
`evidence --phase red` для `declared` задачи отказывает. Пройдено штатно, но через человека: `state …
blocked` → `decide --task … --status reopened --note …` → коммит артефактов Specify → Red заново.

## Почему это стоит разобрать

- `deltafuse evidence` принял Red как authentic, а гейт отверг его по `changed_paths` — отказ узнаётся на шаг
  позже, когда отмотать уже нельзя.
- Навыки `specify` и `declare` нигде не говорят закоммитить артефакты Specify перед Red; малой модели это не
  вывести.

## Варианты (решение владельца)

1. `evidence --phase red` отказывает сразу, назвав файлы вне контракта Declare (тот же отказ, но на шаг раньше,
   пока Red можно взять заново);
2. `changed_paths` Red считать от базы, включающей артефакты Specify (коммит или снимок при `specified`);
3. строка в навыке `declare` (и `specify`): «закоммить артефакты Specify до Red».

Источник: `fuseback/docs/planning/E2E-CHANGE-J03.md`, раздел «Второй прогон», пункт 4.
