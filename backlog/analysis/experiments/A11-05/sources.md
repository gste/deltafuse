# Источники A11-05 — первичные практики по находкам A02–A07

Проверено 2026-09-08. Это **не** пятый SDD-фреймворк: точечная сверка **именованных** практик плана A11 с уже доказанными находками. Популярность не proof. Длинные цитаты и шаблоны не копировались.

Пакетный путь `backlog/analysis/criteria.md` отсутствует; критерии — [backlog/criteria.md](../../../criteria.md). Контракты DF — [backlog/matrices/contracts.md](../../matrices/contracts.md). Границы: [plan-review.md](../../plan-review.md) (A10–A11: четыре аналога + первичные практики).

Аналоги A11-01…A11-04 **не переранжировать**. Находки A09 (F-006…F-010) вне скоупа, кроме уже запаркованных Q.

## Pin

Контрактная сверка; git-релиз «практики» нет. Ревизия репозитория на старте: `ac484b2`. LLM не вызывали. Инструменты (PIT, Hypothesis, Pact, Cucumber) **не ставили**.

## URL и разделы

| ID | URL | Дата / pin | Раздел / смысл |
|---|---|---|---|
| PP-S1 | https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions | 2011-11-15; авторский отказ от copyright на этот пост | ADR: title, context, decision, status, consequences; статусы proposed / accepted / deprecated / **superseded** |
| PP-S2 | https://dannorth.net/blog/introducing-bdd/ | 2006-09-20 | BDD: Given / When / Then как язык примеров поведения, не отдельный инструмент |
| PP-S3 | https://www.rfc-editor.org/rfc/rfc2119.html | RFC 2119, March 1997, BCP 14 | MUST / MUST NOT / SHOULD / MAY |
| PP-S4 | https://doi.org/10.1109/RE.2009.9 | IEEE RE 2009; IEEE Xplore 5328509 | EARS (Mavin et al.): WHEN … THE SYSTEM SHALL. PDF **paywalled** — цитировать DOI, не текст статьи |
| PP-S5 | https://pitest.org/quickstart/mutators/ | docs 2026-09-08 | PIT: bytecode mutators (conditionals, returns, math); score = killed / total. Не ставить в ядро DF |
| PP-S6 | https://hypothesis.readthedocs.io/en/latest/ | fetch timeout 2026-09-08; страница жива как docs Hypothesis | PBT / shrinking. Класс практики: QuickCheck (Claessen & Hughes, ICFP 2000), не продукт Kiro |
| PP-S7 | https://reproducible-builds.org/docs/definition/ | docs 2026-09-08 (URL `.../definitions/` — 404) | Bit-identical artifacts from same source. CC BY-SA 4.0 |
| PP-S8 | https://git-scm.com/docs/gitattributes | Git docs 2026-09-08 | `text` / `eol=lf` нормализует EOL в индексе; `*.sh text eol=lf` |
| PP-S9 | https://csrc.nist.gov/pubs/sp/800/128/upd1/final | SP 800-128, Aug 2011; update 2019-10-10 | Security-focused configuration / change control: авторизация изменения, baseline, audit trail |
| PP-S10 | https://owasp.org/www-community/attacks/Path_Traversal | OWASP community, сверка 2026-09-08 | Path traversal: каноникализация и проверка, что путь внутри корня |
| PP-S11 | https://docs.pact.io/getting_started/how_pact_works | Pact docs, сверка 2026-09-08 | Consumer-driven contract tests между сервисами |

Внутренние находки DF (не внешние URL): [F-001](../../../findings/F-001.md), [F-002](../../../findings/F-002.md), [F-003](../../../findings/F-003.md), [F-004](../../../findings/F-004.md), [F-005](../../../findings/F-005.md), [A07-03](../A07-03/result.md).

## Лицензия и копирование

| Источник | Лицензия / статус | Копирование в DF |
|---|---|---|
| Nygard ADR post | отказ от copyright на этот пост (CC0-класс) | цитировать статусы; **не** подменять `decision.schema.yaml` шаблоном блога |
| Dan North BDD | copyright автора | идея GWT; **не** копировать эссе |
| RFC 2119 | IETF | уже SPEC-003 |
| EARS IEEE | copyright IEEE | DOI only |
| PIT | Apache-2.0 (проект) | **не** вендорить PIT |
| Hypothesis / QuickCheck | docs copyright / academic paper | метод, не раннер |
| Reproducible Builds definition | CC BY-SA 4.0 | определение; DF не binary build |
| NIST SP 800-128 | работа US government (public domain US) | идея change control, не ITIL-ритуал |
| Git gitattributes | документация Git | практика EOL |
| Pact | docs Pact Foundation | **не** переносить |
| OWASP Path Traversal | community docs | каноникализация путей |

## Не использовано как proof

- Популярность Cucumber / JBehave / PIT / Pact.
- Повторный рейтинг Spec Kit / OpenSpec / BMAD / Kiro.
- Полный PDF IEEE RE 2009 и полный PDF NIST 800-128 (страница публикации достаточна для класса практики).
- Установка mutator-раннеров и property-раннеров.
- F-006…F-010 как новые строки этой карточки.
