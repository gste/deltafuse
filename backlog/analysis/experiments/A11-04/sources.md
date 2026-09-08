# Источники A11-04 — Kiro Specs

Проверено 2026-09-08. Kiro — **управляемый продукт** (AWS). Публичные docs отделены от недоступных внутренних механизмов (генератор PBT, планировщик волн задач, модель). Популярность и маркетинг не proof. Длинные примеры spec не копировались (copyright docs).

Пакетный путь `backlog/analysis/matrices/contracts.md` отсутствует; контракты DF — [backlog/matrices/contracts.md](../../matrices/contracts.md).

## Pin

| Что | Значение | Дата |
|---|---|---|
| Docs (вход карточки) | https://kiro.dev/docs/specs/ | Page updated **2026-08-27** |
| Feature Specs | https://kiro.dev/docs/specs/feature-specs/ | Page updated **2026-08-04** |
| Analyze Requirements | https://kiro.dev/docs/specs/analyze-requirements/ | Page updated **2026-09-02** |
| Correctness (PBT) | https://kiro.dev/docs/specs/correctness/ | Page updated **2026-08-04** |
| Open-source release | **нет** публичного git/commit | — |
| Лицензия продукта | proprietary (Kiro IDE/CLI/Web); SPDX не опубликован | docs 2026-09-08 |
| EARS | публичная нотация требований (не собственность Kiro) | цитировать метод, не шаблоны `.kiro/` |

Внутренности runtime **not-tested** / недоступны: как строится DAG волн, как извлекаются properties, какая модель. Не утверждать гарантии, которых нет в docs.

## URL и разделы

| ID | URL | Дата docs | Раздел / смысл |
|---|---|---|---|
| KI-S1 | https://kiro.dev/docs/specs/ | 2026-08-27 | Три файла: `requirements.md` / `bugfix.md`, `design.md`, `tasks.md`; фазы Requirements → Design → Tasks; Quick Spec без approval gates; parallel task waves (IDE/CLI/Web) |
| KI-S2 | https://kiro.dev/docs/specs/feature-specs/ | 2026-08-04 | Requirements-First vs Design-First; EARS `WHEN … THE SYSTEM SHALL`; Analyze Requirements до design |
| KI-S3 | https://kiro.dev/docs/specs/analyze-requirements/ | 2026-09-02 | Cross-requirement: inconsistencies, ambiguities, conflicts, unstated assumptions, missing edges; LLM questions, не schema gate |
| KI-S4 | https://kiro.dev/docs/specs/quick-spec/ | 2026-08-04 | Один проход без гейтов между фазами; те же три файла |
| KI-S5 | https://kiro.dev/docs/specs/best-practices/ | 2026-08-04 | Quick Spec vs gates; Analyze после Quick Spec; Sync Files; `#spec` грузит все три файла в чат |
| KI-S6 | https://kiro.dev/docs/specs/bugfix-specs/ | 2026-08-04 | Current / expected / unchanged behavior; PBT на fix + regression |
| KI-S7 | https://kiro.dev/docs/specs/correctness/ | 2026-08-04 | PBT из EARS; optional; не formal verification; IDE only (не CLI/Web/Mobile) |
| KI-S8 | https://kiro.dev/docs/getting-started/first-project/ | 2026-09-02 | Три фазы specs в продукте Kiro |

## Лицензия и копирование

Шаблоны `.kiro/specs/` и тексты docs — не MIT. Копировать в DeltaFuse **нельзя**. EARS как метод формулировки (WHEN/SHALL) можно обсуждать независимо от Kiro. PBT — общеизвестная практика (Hypothesis и т.п.), не «Kiro-only».

## Не использовано как proof

- AWS Builder Center блог, сторонние сравнения (specs.md vs Kiro).
- Установка Kiro, живой IDE, недоступный runtime.
- Качество vs ornith (A11-06): Kiro привязан к своей IDE/модели.
