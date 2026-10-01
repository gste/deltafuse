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

## Прочее

- [ ] Add python 3.15 support


## Framework changes

- [x] Schema-driven Artifact Writer — 47/49 карточек закрыты, реализация и тесты
  завершены. Два оставшихся блокера перенесены в roadmap q0; эпик подлежит
  закрытию и удалению по [ревизии](roadmap/REVISION-aw.md).
