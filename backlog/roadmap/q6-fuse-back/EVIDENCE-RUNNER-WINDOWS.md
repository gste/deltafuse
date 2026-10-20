# q6: `deltafuse evidence` не находит `mvn` на Windows

**Состояние: сделано 2026-10-08, ветка `fix/evidence-runner-windows`.** Отличие от постановки: подставляется только найденный `.cmd`/`.bat` — поиск `python` по PATH на Windows нашёл бы не тот интерпретатор (ярлык WindowsApps вместо venv), а CreateProcess сначала ищет в каталоге запущенного Python; не найденный `which` раннер запускается как есть, и только при неудаче пишется «runner `mvn` not found on PATH». Аргументы с `& | < > ^ %` для пакетного раннера отклоняются: cmd.exe читает их сам. Было: постановка, к исполнению в отдельном чате DeltaFuse. Записано 2026-10-08 по сквозному Change на
JVM (`fuseback/docs/planning/E2E-CHANGE-J03.md`, раздел J01). Независимо от
[CHANGE-WRITE-PATHS](CHANGE-WRITE-PATHS.md).

## Проблема

`core/evidence.py` запускает команду теста как `subprocess.run(run_argv, …)` (:195, :501) без поиска
исполняемого файла. На Windows Maven и Gradle — это `mvn.cmd`, `gradle.bat`, `gradlew.bat`: `CreateProcess` их по
имени `mvn` не находит. Итог — `[WinError 2]`, `exit_code: 127`, `failure_category: fixture-error`, и ни Red, ни
Green для Java-продукта на Windows не записываются, хотя `workflow.test_commands: [mvn -B test]` — ровно то,
что `runners.py` (:31, `JVM_RUNNERS`) и навыки называют разрешённым раннером.

Наблюдение (DeltaFuse 3.3.7 на `bfcf4d5`, Windows 11, Maven 3.9.12, J01 после Fuse-Back):

```
deltafuse evidence docs/changes/CHG-001-cooldown-penalty --phase red --task TASK-001 -- mvn -B test
Evidence is not authentic:
  - Red failure_category is 'fixture-error', not 'behavioral-mismatch': no AssertionError in the output, ...
    last error line: [WinError 2] Не удается найти указанный файл
```

С `-- mvn.cmd -B test` тот же Red — `behavioral-mismatch`, `Evidence is authentic` (allowlist имя `mvn.cmd`
принимает). Но `mvn.cmd` в `workflow.test_commands` ломает Linux и CI, поэтому обход в продукте неверен.

## Решение

Перед `subprocess.run` разрешать `argv[0]` через `shutil.which` (на Windows он учитывает `PATHEXT`: `.cmd`,
`.bat`, `.exe`); найденный путь подставлять в запуск, а в записи evidence оставлять argv как его дал Worker.
Не найден — прежнее поведение (127 и понятное сообщение «runner `mvn` not found on PATH»). `shell=True` не
использовать.

Проверить и другие места, где ядро само запускает команду теста или раннер (`grep subprocess.run src/deltafuse`):
то же правило.

## Красные тесты

1. на Windows (или с подменой `shutil.which`/`os.name`) `evidence` с argv `["mvn", "-B", "test"]` запускает
   разрешённый путь `…\mvn.cmd`; в записи `command` остаётся `mvn -B test`;
2. не найденный раннер даёт 127 и сообщение с его именем, не `WinError 2`;
3. Linux/macOS: поведение не меняется.

## Критерий приёмки

Тесты зелёные, полный набор зелёный; `CHANGELOG.md` — запись. На Windows с Maven: Red/Green/regression для
бенча J01 записываются командой `mvn -B test` без `.cmd`.

Источник: `fuseback/docs/planning/E2E-CHANGE-J03.md`, раздел «Третий прогон: JVM (J01)».
