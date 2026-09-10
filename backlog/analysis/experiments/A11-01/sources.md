# Источники A11-01 — GitHub Spec Kit

Проверено 2026-09-08. Популярность (звёзды, число интеграций) не является доказательством пользы для DeltaFuse. Тексты шаблонов не копировались: только URL, pin и краткий смысл раздела.

Пакетный путь `backlog/analysis/matrices/contracts.md` отсутствует; контракты DF — [backlog/matrices/contracts.md](../../matrices/contracts.md).

## Pin

| Что | Значение | Дата |
|---|---|---|
| Репозиторий | https://github.com/github/spec-kit | — |
| Latest release | **v1.0.4** (`https://github.com/github/spec-kit/releases/tag/v1.0.4`) | published 2026-09-02T21:06:05Z |
| Commit тега v1.0.4 | `cb610277fdea781fcfa83d20522c2db37c94068d` | 2026-09-02 |
| `main` HEAD на момент сверки | `4a7341a93d944d6efe153b71da4a1adb9c2b578c` (newsletter) | `pushed_at` 2026-09-04T11:51:20Z |
| Лицензия | MIT, Copyright GitHub, Inc. | `LICENSE` на v1.0.4 |
| Docs site | https://github.github.io/spec-kit/ | landing + integrations |

Цепочка шагов 0–5 совпадает на `v1.0.4` README и на `main` README; сравнение контрактов опирается на **v1.0.4**. Docs site обновляется отдельно от тега; внутренние механизмы CLI, не описанные в этих страницах, не утверждаются.

## URL и разделы

| ID | URL | Pin | Раздел / смысл |
|---|---|---|---|
| SK-R1 | https://raw.githubusercontent.com/github/spec-kit/v1.0.4/README.md | v1.0.4 / `cb610277` | «SDD Quickstart»: 0 constitution, 1 specify, 2 plan, 3 tasks, 4 implement, 5 converge; цикл 4–5 до Converged |
| SK-R2 | тот же README | v1.0.4 | «Available Slash Commands»: core `/speckit.constitution` … `/speckit.converge`; optional `/speckit.clarify`, `.analyze`, `.checklist` |
| SK-R3 | тот же README | v1.0.4 | «Making Spec Kit Your Own»: extensions / presets / bundles; bug и assess — **opt-in** |
| SK-R4 | тот же README | v1.0.4 | «License» → MIT; «Supported AI Coding Agent Integrations» → список в docs, не llama-server |
| SK-D1 | https://raw.githubusercontent.com/github/spec-kit/v1.0.4/spec-driven.md | v1.0.4 | `/speckit.specify` → `specs/…/spec.md`; `/plan` → `plan.md` + constitution check; `/tasks` читает `plan.md`, пишет `tasks.md` |
| SK-D2 | тот же spec-driven.md | v1.0.4 | «Constitutional Compliance Through Gates»: чеклисты в шаблоне плана (simplicity / anti-abstraction); LLM самоотчёт, не независимый oracle |
| SK-D3 | тот же spec-driven.md | v1.0.4 | «The Constitutional Foundation»: `memory/constitution.md`; статьи I–III заданы методологией; IV–VI — слоты проекта; `/speckit.analyze` сверяет конкретную constitution |
| SK-L1 | https://raw.githubusercontent.com/github/spec-kit/v1.0.4/LICENSE | v1.0.4 | MIT; копирование шаблонов допустимо **с** сохранением copyright notice |
| SK-I1 | https://github.github.io/spec-kit/reference/integrations.html | docs 2026-09-08 | 38+ агентов + ключ `generic` (`--commands-dir`). **Нет** `llama-server` / ornith. Cursor = `cursor-agent` |
| SK-A1 | https://api.github.com/repos/github/spec-kit | REST 2026-09-08 | `license.spdx_id: MIT`; `stargazers_count` ~133929 — **не** evidence качества |
| SK-A2 | https://api.github.com/repos/github/spec-kit/releases/tags/v1.0.4 | REST 2026-09-08 | published_at, tag → commit `cb610277` |

## Не использовано как proof

- Число звёзд, forks, «38 integrations», anniversary 1.0.0.
- Установка `specify-cli`, живой прогон slash-команд, копирование `templates/**`.
- Сравнение качества генерации vs ornith (это A11-06, и только при сопоставимой интеграции).
