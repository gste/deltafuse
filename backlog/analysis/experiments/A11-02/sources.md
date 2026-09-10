# Источники A11-02 — OpenSpec

Проверено 2026-09-08. Популярность (звёзды, npm downloads) не является доказательством пользы для DeltaFuse. Шаблоны и длинные примеры spec не копировались: URL, pin и смысл раздела.

Пакетный путь `backlog/analysis/matrices/contracts.md` отсутствует; контракты DF — [backlog/matrices/contracts.md](../../matrices/contracts.md).

## Pin

| Что | Значение | Дата |
|---|---|---|
| Репозиторий | https://github.com/Fission-AI/OpenSpec | — |
| Docs site | https://openspec.dev/ | homepage репозитория |
| Latest release | **v1.12.0** (`https://github.com/Fission-AI/OpenSpec/releases/tag/v1.12.0`) | published 2026-09-03T00:09:15Z |
| Commit тега / `main` HEAD | `e062b9572be933564ba3899d059377dfa1393e32` | 2026-09-03T00:00:56Z |
| Лицензия | MIT, Copyright (c) 2024 OpenSpec Contributors | `LICENSE` на v1.12.0 |
| npm | `@fission-ai/openspec` | не ставили |

`main` на сверке совпадает с v1.12.0. GitHub `pushed_at` 2026-09-07 может относиться к другим refs; сравнение опирается на **v1.12.0**. CLI/runtime, не описанные в этих страницах, не утверждаются.

## URL и разделы

| ID | URL | Pin | Раздел / смысл |
|---|---|---|---|
| OS-R1 | https://raw.githubusercontent.com/Fission-AI/OpenSpec/v1.12.0/README.md | v1.12.0 / `e062b957` | Философия brownfield; цикл `/opsx:propose` → `apply` → `archive`; папка `openspec/changes/<id>/` (proposal, specs, design, tasks); archive обновляет specs |
| OS-R2 | тот же README | v1.12.0 | «Work fluidly — no rigid phase gates»; сравнение со Spec Kit («rigid phase gates»); рекомендует Codex 5.5 / Opus 4.7 |
| OS-G1 | https://raw.githubusercontent.com/Fission-AI/OpenSpec/v1.12.0/docs/getting-started.md | v1.12.0 | Структура `openspec/specs/` vs `changes/`; delta `ADDED`/`MODIFIED`/`REMOVED`; archive: append / replace / delete в main spec, папка в `changes/archive/` |
| OS-G2 | тот же getting-started | v1.12.0 | Default path включает `/opsx:sync` перед archive; expanded: `/opsx:verify` |
| OS-O1 | https://raw.githubusercontent.com/Fission-AI/OpenSpec/v1.12.0/docs/overview.md | v1.12.0 | «Enablers, not gates»; archive «folds the change back into the truth» |
| OS-E1 | https://raw.githubusercontent.com/Fission-AI/OpenSpec/v1.12.0/docs/existing-projects.md | v1.12.0 | Brownfield: не специфицировать весь код; specs растут одним change; delta-first; `/opsx:explore` читает код |
| OS-T1 | https://raw.githubusercontent.com/Fission-AI/OpenSpec/v1.12.0/docs/supported-tools.md | v1.12.0 | 30+ IDE/CLI агентов; Cursor; shared `.agents`; **нет** llama-server / ornith |
| OS-L1 | https://raw.githubusercontent.com/Fission-AI/OpenSpec/v1.12.0/LICENSE | v1.12.0 | MIT; копирование с copyright notice |
| OS-A1 | https://api.github.com/repos/Fission-AI/OpenSpec | REST 2026-09-08 | `license.spdx_id: MIT`; stars ~67578 — **не** evidence |
| OS-A2 | https://api.github.com/repos/Fission-AI/OpenSpec/releases/tags/v1.12.0 | REST 2026-09-08 | Findings reports; code-grounded planning |

## Не использовано как proof

- Stars, Discord, «most loved», сравнение README vs Spec Kit/Kiro как ranking.
- Установка npm CLI, живой `/opsx:*`, копирование skills.
- Качество генерации vs ornith (A11-06). `concepts.md` на v1.12.0 не удалось скачать (timeout); механика delta/archive взята из getting-started/overview.
