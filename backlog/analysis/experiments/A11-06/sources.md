# Источники A11-06 — сопоставимость двух аналогов на S02/S04/S05

Проверено 2026-09-08. Живой прогон аналогов **не** выполнялся. Популярность и IDE-интеграции не proof качества vs ornith. Шаблоны не копировались. Tools (specify-cli, OpenSpec CLI, BMAD installer, Kiro) **не ставили**.

Пакетный путь `backlog/analysis/experiments/protocol.md :: сопоставимость` **не существует** как заголовок; взяты §1 (calibration/holdout) и §4 (SUT `:1240`, бюджеты). `backlog/analysis/criteria.md` нет — [backlog/criteria.md](../../../criteria.md).

Pins аналогов не переснимались: A11-01…A11-04.

## Pin SUT (не аналог)

| Что | Значение | Дата |
|---|---|---|
| Endpoint | `GET http://127.0.0.1:1240/v1/models` | 2026-09-08, reachable |
| Model | `ornith-1.5-35b-a3b` Q4_K_M, `n_ctx` 33024 | meta llama-server |
| Протокол | [protocol.md](../protocol.md) §4 | frozen A09; Studio `:1234` не SUT |

Доступность модели **не** равна сопоставимой интеграции аналога.

## Кандидаты (два из четырёх)

| # | Аналог | Почему в пару | Почему не живой прогон |
|---|---|---|---|
| 1 | OpenSpec v1.12.0 | Change-папка + archive ближе всего к DF CHG-*; brownfield S02/S05 | OS-T1: нет llama-server; README рекомендует Codex/Opus (OS-R2) |
| 2 | Spec Kit v1.0.4 | Единственный явный BYO-хук `generic --commands-dir` (SK-I1); цепочка spec/plan/tasks | SK-I1: нет llama-server/ornith; `generic` не проверяли установкой |

Не выбраны:

| Аналог | Причина |
|---|---|
| BMAD v6.12.0 | Installer Claude Code/Cursor; нет generic-хука под `:1240` (BM-07). Right-size → Q-001, не runner S02/S04/S05 |
| Kiro Specs | **not-applicable**: IDE/модель продукта (KI-09) |

Homemade SDD vs DF на том же SUT уже есть — [A10-01](../A10-01/result.md). Это **не** Spec Kit и **не** OpenSpec; повтор не заменяет A11-06.

## URL и разделы (сопоставимость)

| ID | URL / путь | Дата | Смысл |
|---|---|---|---|
| CMP-P1 | `backlog/analysis/experiments/protocol.md` §1 | A08 | S02/S04 calibration; S05 holdout — нельзя подкручивать промпты аналога по S05 |
| CMP-P2 | тот же файл §4 | A09 frozen | SUT `:1240`, n=3, oracles вне prompt, max_retries 3 |
| CMP-P3 | `GET /v1/models` `:1240` | 2026-09-08 | ornith доступен; аналог не подключён |
| CMP-S02 | [A09-13](../A09-13/result.md), local-results | 2026-09-08 | S02 `partial` (F-008/F-009, 0 Verify) |
| CMP-S04 | то же | 2026-09-08 | S04 `pass` (`blocked-on-decision`) |
| CMP-S05 | A09-13 + [A10-01](../A10-01/result.md) | 2026-09-08 | Holdout Specify/F-010; SDD даёт файлы, не hidden-green |
| CMP-SK | [A11-01/sources.md](../A11-01/sources.md) SK-I1, SK-05 | 2026-09-08 | Integrations; clarify ≠ FSM |
| CMP-OS | [A11-02/sources.md](../A11-02/sources.md) OS-T1, OS-R2, OS-05 | 2026-09-08 | Tools list; no gates; Opus/Codex |

## Лицензия

Без копирования. MIT Spec Kit / OpenSpec уже в A11-01/02. Живой прогон всё равно не лицензирует «тот же SUT».

## Не использовано как proof

- Установка CLI и обёртка slash-команд вокруг `:1240` (это был бы третий харнесс, как A10-01).
- Качество Copilot/Claude/Opus vs ornith.
- Повторный рейтинг строк SK/OS/BM/KI.
