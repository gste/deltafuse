# Источники A11-03 — BMAD Method

Проверено 2026-09-08. Популярность (звёзды, Discord) не является доказательством пользы для DeltaFuse. Skills и длинные шаблоны не копировались. Документация — управляемый продукт: отделяем опубликованные инструкции от непроверенного runtime установщика.

Пакетный путь `backlog/analysis/matrices/contracts.md` отсутствует; контракты DF — [backlog/matrices/contracts.md](../../matrices/contracts.md).

## Pin

| Что | Значение | Дата |
|---|---|---|
| Репозиторий | https://github.com/bmad-code-org/BMAD-METHOD | — |
| Docs site | https://docs.bmad-method.org/ | fetch 2026-09-08 |
| Latest release | **v6.12.0** (`https://github.com/bmad-code-org/BMAD-METHOD/releases/tag/v6.12.0`) | published 2026-09-04T02:31:25Z |
| Commit тега v6.12.0 | `05bfbd46d00766ec88eb9b42e76be2c575d64d7b` | 2026-09-04 |
| `main` HEAD на сверке | `abe4eb1bce919c9d22cd18b3519353d5824c4b75` | после тега; docs site может быть новее тега |
| Код | MIT, Copyright (c) 2025 BMad Code, LLC | `LICENSE` на v6.12.0 |
| Товарные знаки | **не** под MIT — `TRADEMARK.md` | v6.12.0 |
| GitHub `license.spdx_id` | `NOASSERTION` (`Other`) из-за trademark notice | REST 2026-09-08 |

Сравнение контрактов опирается на **v6.12.0** + страницы docs, согласованные с release notes («Build decides how much ceremony after investigating»). `npx bmad-method install` и `--list-tools` **не** запускали.

## URL и разделы

| ID | URL | Pin | Раздел / смысл |
|---|---|---|---|
| BM-R1 | https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/v6.12.0/README.md | v6.12.0 / `05bfbd46` | Right-sized process; small → build, complex → deeper planning; durable context; specialized perspectives; ссылка Choose a Planning Path |
| BM-D1 | https://docs.bmad-method.org/plan/choose-a-planning-path/ | docs 2026-09-08 | Глубина по определённости intent; `bmad-spec` потолок «tens of thousands of tokens»; epic vs project (~20 sessions); `bmad-build-auto` после стабилизации решений |
| BM-D2 | https://docs.bmad-method.org/build/build-a-change/ | docs 2026-09-08 | `bmad-build`: investigate codebase → light vs full plan (intent gaps / irreversible / footprint); self-review; skip process for trivial; recommends subagents |
| BM-D3 | https://docs.bmad-method.org/plan/define-requirements-and-a-specification/ | docs 2026-09-08 | `SPEC.md` five fields; только `bmad-spec` пишет spec; optional `stories.yaml` |
| BM-D4 | https://docs.bmad-method.org/existing-codebases/set-and-maintain-project-context/ | docs 2026-09-08 | `bmad-project-context` → короткий блок в `AGENTS.md`; human approve; не копировать дерево репо |
| BM-D5 | https://docs.bmad-method.org/ (landing) | docs 2026-09-08 | Skills в Claude Code / Cursor; thinking vs `bmad-build`; small fix без planning |
| BM-D6 | https://docs.bmad-method.org/start/install-bmad/ | docs 2026-09-08 | `npx bmad-method install`; `--list-tools` (не запускали); Node 20 + Python + uv |
| BM-L1 | https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/v6.12.0/LICENSE | v6.12.0 | MIT + trademark notice в том же файле |
| BM-L2 | https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/v6.12.0/TRADEMARK.md | v6.12.0 | Знаки BMad не лицензированы MIT; форк под другим именем |
| BM-A1 | https://api.github.com/repos/bmad-code-org/BMAD-METHOD | REST 2026-09-08 | stars ~52769 — **не** evidence; license Other |
| BM-A2 | https://api.github.com/repos/bmad-code-org/BMAD-METHOD/releases/tags/v6.12.0 | REST 2026-09-08 | Ceremony after investigation; review triage; Polytoken/Grok/ZCode в installer |

## Не использовано как proof

- Stars, Discord, YouTube, «always free».
- Установка `_bmad`, живые slash-skills, `bmad-loop`.
- Качество vs ornith (A11-06). Внутренние файлы skills в репозитории не читались целиком.
