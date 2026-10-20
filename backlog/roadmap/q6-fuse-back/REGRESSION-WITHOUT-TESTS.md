# q6: regression принят, хотя не выполнен ни один тест (Gradle UP-TO-DATE)

**Состояние: сделано 2026-10-20 (вариант 1 с подсказкой из варианта 3, решение владельца), ветка `fix/regression-needs-report`.** Для pytest, Maven и Gradle прошедший Green, regression или verification без свежего отчёта раннера (или с отчётом без единого прошедшего или упавшего теста) отвергается и при записи, и на каждом шлюзе; если в логе Gradle `UP-TO-DATE`/`FROM-CACHE`, отказ называет `--rerun`. Команду Worker'а ядро не меняет. Не закрыто: многомодульная сборка, где Gradle пропустил часть модулей, оставляет свежий, но неполный отчёт - тут помогает только `--rerun`. Было: наблюдение, к разбору. Записано 2026-10-09 по сквозному Change на Gradle-варианте J01
(`fuseback/docs/planning/E2E-CHANGE-J03.md`, раздел Gradle). DeltaFuse `578ffed` + `caf014a`.

## Что произошло

`workflow.test_commands: [gradle --no-daemon test]`. Green выполнил тесты. Сразу за ним regression той же командой:
Gradle счёл задачу `test` актуальной (`> Task :test UP-TO-DATE`) и не запустил ни одного теста. Запись regression —
`exit_code: 0`, `result: passed`, `Evidence is authentic`; `implemented` прошёл. Отказал только `converged`, и то
по verification-прогону («the verification run has no runner report, so it does not show which tests it ran»).

То есть regression без единого выполненного теста засчитывается; поймал это лишь следующий шлюз.

## Почему важно

Regression — доказательство, что изменение не сломало остальное. Пропущенный запуск выглядит как зелёный. С
Maven (Surefire всегда исполняет тесты) этого не видно; с Gradle — каждый раз, когда код между Green и regression
не менялся (обычный случай).

## Варианты (решение владельца)

1. Regression, как verification, требует отчёт раннера со свежими результатами (новее начала прогона); без него —
   не authentic, с понятной причиной («the runner ran no test: Gradle reported the test task up to date»).
2. Для Gradle добавлять `--rerun` к `test`, если его нет (менее прозрачно: ядро меняет команду Worker'а).
3. Строка в навыке `implement`/`verify` и в документации раннеров: Gradle — с `--rerun`.

Fuse-Back со своей стороны теперь пишет `gradle --no-daemon test --rerun` (находка 47), но ядро не должно
полагаться на то, что команда так записана.
