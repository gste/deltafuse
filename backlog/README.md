# DeltaFuse backlog

Здесь находится только живая очередь работ. Завершённые задачи сохраняются в истории Git.

## Roadmap

- [ ] [Путь к стабильной версии на моделях 35–70B](roadmap/README.md) — нулевой
  пункт (qualification baseline) и пять направлений в порядке исполнения.
  Промпты по лестнице тиров: [q4 — analyze/routing](roadmap/q4-analyze-routing/),
  [q6 — Fuse-Back](roadmap/q6-fuse-back/).

- [x] [q6: корень `dir/*` — владение файлами, лежащими прямо в каталоге](roadmap/q6-fuse-back/CODE-ROOT-DIRECT-FILES.md) —
  принято и реализовано в 3.3.6. Без него ядро пакета остаётся без
  владельца, как только его подкаталоги нужны другой capability (Markdown: 13
  из 35 файлов; на JVM это родительские пакеты).
- [x] [q6: regression принят без единого выполненного теста](roadmap/q6-fuse-back/REGRESSION-WITHOUT-TESTS.md) —
  наблюдение 2026-10-09: Gradle `test` UP-TO-DATE после Green, regression `passed`, поймал только `converged`.
  Сделано 2026-10-20: прогон без выполненных тестов не доказательство (ветка `fix/regression-needs-report`).
- [x] [q6: у вердикта Verify `spec-gap` нет пути назад](roadmap/q6-fuse-back/SPEC-GAP-NO-ROUTE.md) —
  наблюдение 2026-10-09: Change с `spec-gap` не может ни сойтись, ни вернуться на Specify; переход
  `verifying -> analyzing` есть в таблице, но команды нет.
  Сделано 2026-10-11: `deltafuse decide --gap spec-gap --status reopened` возвращает Change на Analyze (`f14261d`).

- [x] [q6: пути записи Change — из `workflow.code_roots`](roadmap/q6-fuse-back/CHANGE-WRITE-PATHS.md) —
  постановка 2026-10-08, решение владельца: делать. На маршруте `code` задача пишет только корневые
  `src/**` и `tests/**`, а объявленный `workflow.code_roots` не действует: Change на многомодульном
  Maven (J03) стоит на `decomposed`.
- [ ] [q6: Red записывает незакоммиченную правку спецификации](roadmap/q6-fuse-back/RED-UNCOMMITTED-SPEC.md) —
  наблюдение 2026-10-08: `evidence` принимает Red, гейт `declaring` его отвергает, отмотать может только
  человек (`reopened`).
- [ ] [q6: `deltafuse evidence` не находит `mvn` на Windows](roadmap/q6-fuse-back/EVIDENCE-RUNNER-WINDOWS.md) —
  постановка 2026-10-08: `subprocess.run` без `shutil.which`, `mvn.cmd` не находится; Red/Green для Java на
  Windows — `fixture-error`.
- [x] [q6: после `decide --gap` шлюз `analyzed` отказывает до коммита](roadmap/q6-fuse-back/GAP-REOPEN-COMMIT.md) —
  наблюдение 2026-10-21: leash называет запись `gap-reopen` «not a Core transition receipt».
- [x] [q6: снимок `declaring` удлиняет пути на Windows](roadmap/q6-fuse-back/SNAPSHOT-LONG-PATHS.md) —
  наблюдение 2026-10-21: `.deltafuse/snapshots/...` + путь теста Fuse-Back, `git add` без `core.longpaths` падает.

## Прочее

- [ ] Add python 3.15 support


## Framework changes

- [x] Schema-driven Artifact Writer — 47/49 карточек закрыты, реализация и тесты
  завершены. Два оставшихся блокера перенесены в roadmap q0; эпик подлежит
  закрытию и удалению по [ревизии](roadmap/REVISION-aw.md).
