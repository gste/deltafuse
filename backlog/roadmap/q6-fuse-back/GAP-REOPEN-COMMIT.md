# q6: после `decide --gap … reopened` шлюз `analyzed` отказывает до коммита — с непонятной причиной

**Состояние: сделано 2026-10-21 (варианты 1 и 2, решение владельца), ветка `fix/fuseback-338`.** Leash знает квитанцию `gap-reopen` и принимает до коммита то, что написал `decide`: файл, байты которого подтверждает квитанция `decide` в журнале гейтов; удалённую запись, чьи байты лежат в архиве переоткрытия с квитанцией; файл продукта, восстановленный к снимку `declaring`. То же для переоткрытия задачи - там была та же дыра. `decide` после переоткрытия печатает «next: commit these changes before the next step». Было: наблюдение, к разбору. Записано 2026-10-21 по проверке 3.3.8 (`aa92be6`) на многомодульном
Maven-варианте J01 после Fuse-Back (`fuseback/docs/planning/E2E-CHANGE-J03.md`, «Седьмой прогон»).

## Что произошло

Verify записал `spec-gap`, человек выполнил `deltafuse decide <change> --gap spec-gap --status reopened --note ...`
(`decide: gap reopened`, `change_status: analyzing`, архив `reopened/verify.1`). Слайс уже называл нужный файл
спецификации, поэтому проход `gap` в Analyze ничего не менял, и Worker сразу выполнил `advance --gate analyzed`:

```
advance failed: gate 'analyzed' refused by the write leash (workflow.leash: enforce):
leash: '.deltafuse/transitions.jsonl' changed outside the deltafuse CLI: line 12 is not a Core transition receipt (DF3-007);
leash: 'docs/changes/.../evidence/green/TASK-001.yaml' is outside the analyze, verify write envelope;
leash: 'docs/changes/.../evidence/regression/TASK-001.yaml' is outside the analyze, verify write envelope;
leash: 'docs/changes/.../spec-delta.md' is outside the analyze, verify write envelope
```

Строка 12 — запись самого `decide` (`"kind": "gap-reopen"`, с `receipt`), а перечисленные файлы переписал (или
переместил в архив) тоже `decide`. После `git commit` этих изменений тот же `advance --gate analyzed` прошёл.

## Почему важно

Сообщение говорит, что журнал правили «outside the deltafuse CLI», хотя это сделал CLI по команде человека; Worker
не поймёт, что нужен всего лишь коммит, и может начать «чинить» журнал. Та же семья, что
[RED-UNCOMMITTED-SPEC](RED-UNCOMMITTED-SPEC.md): незакоммиченная запись ядра.

## Варианты (решение владельца)

1. Leash узнаёт запись `gap-reopen` как запись Core и файлы, которые `decide --gap` переписал, — как запись человека
   (как уже делает для архива verify).
2. `decide --gap` в конце печатает «commit these changes before the next step».
3. Строка в навыке analyze для прохода `gap`.
