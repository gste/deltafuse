# Backlog

Очередь работ вокруг канонического репозитория DeltaFuse. Это не lifecycle продукта и не замена `docs/**`.

Брать в работу:

| ID | Статус | Слой |
|---|---|---|
| [SK-001](product/SK-001.md) | `planned` | schemas / templates / skills — первый `check-gate` |
| [HS-001](product/HS-001.md) | `planned` | контракт хоста (`halt.choices`, pack isolation, Human Gates) |

Сводка: [product/index.md](product/index.md).

Закрытые карточки, пакеты анализа, findings, матрицы и снимки экспериментов остаются в git history.

Последний коммит с полным деревом экспериментов: `e3e1149`.

```text
git log -- backlog/
git show e3e1149:backlog/analysis/experiments/A09-01/result.md
```

Не восстанавливать `backlog/analysis/experiments/**/work/**` в рабочее дерево: Cursor индексирует вложенные `AGENTS.md` и `.cursor/skills/**` как скиллы воркспейса.
