# Backlog

Очередь работ вокруг канонического репозитория DeltaFuse. Это не lifecycle продукта и не замена `docs/**`.

**Пусто.** Брать в работу нечего. Закрытые карточки, пакеты анализа, findings, матрицы и снимки экспериментов остаются в git history.

Последний коммит с полным деревом экспериментов: `e3e1149`.

```text
git log -- backlog/
git show e3e1149:backlog/analysis/experiments/A09-01/result.md
```

Не восстанавливать `backlog/analysis/experiments/**/work/**` в рабочее дерево: Cursor индексирует вложенные `AGENTS.md` и `.cursor/skills/**` как скиллы воркспейса.
