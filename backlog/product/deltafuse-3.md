# DeltaFuse 3.0 — программа модернизации

- **Статус:** `active`
- **Версия-цель:** `3.0.0`
- **Источник:** [AU-001](AU-001.md) и [audit-report.md](audit-report.md)
- **Следующий шаг:** [DF3-006](DF3-006.md)

DeltaFuse 3.0 — breaking-линия, в которой Core становится единственным авторитетом lifecycle-переходов, доказательств и Human Gate receipts. Главная задача framework — обеспечивать качественную реализацию на локальных LLM класса 35B A3B и выше даже при полном context window от 32k. Это не повод ослаблять Process или переносить продуктовые требования во framework.

## Зафиксированные решения

1. Референсный нижний класс Worker — локальная LLM 35B A3B; первая qualification model — `ornith-1.5-35b-a3b` через LM Studio. Cloud или более крупная модель не требуется для корректного прохождения Process.
2. Полный вызов должен помещаться в context window 32k. Framework-controlled input по умолчанию ограничен 16k токенов и 24 уникальными файлами, оставляя запас host/system instructions, tool exchange и ответа.
3. Lifecycle остаётся `Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`.
4. `Red` и `Green` остаются evidence states, не lifecycle steps.
5. Worker пишет содержательные Change-артефакты, но не подтверждает собственный прогресс.
6. Core валидирует gate, выполняет переход и выдаёт проверяемый receipt. Ручная смена status без соответствующего receipt не принимается.
7. Human Gates: Decision, spec accept и merge. Core журналирует Decision/spec; merge остаётся внешней обязанностью host/человека.
8. Локальный hash chain защищает только от случайной порчи. Защита от подделки требует подписи доверенного host broker с ключом вне Worker write/read surface.
9. Официально поддерживаются nested source checkout и wheel. Wheel содержит сгенерированный при build immutable runtime bundle; канонический источник остаётся в `process/**`, а `docs/**` не копируется в продукт.
10. `check-gate` и `next` остаются read-only. Изменение lifecycle state выполняет отдельный Core command.
11. `init --force` не переставляет evidence stamps. Update между несовместимыми v3 contract revisions при активных Changes останавливается до явного закрытия или переноса Change и повторного evidence run.
12. v3 поддерживает только contracts и терминологию v3. Совместимость, миграция и qualification предыдущих версий не входят в эту программу.

## Small-LLM Quality Contract

- Один Worker-вызов решает одну capability, один artifact layer и один проверяемый outcome.
- `next` передаёт точные bounded reads; ни один шаг не требует загрузки всего репозитория, всего `docs/spec/**` или соседних Changes.
- Core выполняет routing mechanics, transition checks, diff calculation и evidence bookkeeping вне prompt модели.
- Receipts, manifests, полные журналы и длинные command outputs не входят в Worker context без явной диагностической необходимости; Core отдаёт краткое структурированное резюме.
- При превышении token/file budget работа декомпозируется. Обрезание обязательного контекста и молчаливое продолжение запрещены.
- Качество измеряется disk-based bench: correctness, завершённые stages, retries, context tokens, уникальные файлы, выдуманные пути и envelope violations.
- DF3-001 фиксирует абсолютные численные release thresholds для v3 до изменения реализации. Порог выводится из требований к качеству и context envelope, а не из результатов предыдущей версии; ослабление требует отдельного maintainer Decision.

## Threat model

DeltaFuse защищается от ошибочного или враждебного Worker, которому host выдал ограниченные read/write/command capabilities. Доверенными считаются Core binary, host broker, выбранный человеком action и закрытый signing key. Полностью скомпрометированные OS, Python environment или maintainer account находятся вне границы. Без host broker CLI работает в `local` integrity profile и честно не заявляет криптографическую защиту Human Gates.

## Очередь реализации

| Порядок | Карточка | Результат | Зависит от |
|---|---|---|---|
| 1 | [DF3-001](DF3-001.md) | ✅ V3 contracts, threat model и воспроизводящие тесты ([v3/](v3/)) | — |
| 2 | [DF3-002](DF3-002.md) | ✅ Archive bypass и docs/ops convergence | DF3-001 |
| 3 | [DF3-003](DF3-003.md) | ✅ CI diff и полный framework manifest/hash | DF3-001 |
| 4 | [DF3-004](DF3-004.md) | ✅ Core-owned transitions и spec rejection loop | DF3-002 |
| 5 | [DF3-005](DF3-005.md) | ✅ Wheel/runtime bundle и безопасный upgrade | DF3-003 |
| 6 | [DF3-006](DF3-006.md) | Evidence command/path authority и task envelope | DF3-004 |
| 7 | [DF3-007](DF3-007.md) | Подписанные Human Gate receipts | DF3-004 |
| 8 | [DF3-008](DF3-008.md) | Schema v3 и Declare contracts | DF3-004, DF3-006, DF3-007 |
| 9 | [DF3-009](DF3-009.md) | 35B/32k qualification, adversarial bench, docs и release | DF3-005, DF3-008 |

## Disposition аудита

| Findings | Решение |
|---|---|
| F-01, F-02 | Приняты; DF3-002 |
| SEC-01, SEC-02 | Приняты; DF3-003 |
| B-01 | Принят, но `package-data` недостаточно; DF3-005 |
| SEC-03, SEC-05 | Угроза принята, hash chain как security fix отклонён; DF3-007 |
| C-01, C-04 | Приняты; DF3-009 и DF3-006 |
| F-03, F-04, F-07 | Объединены в Core-owned transition model; DF3-004 |
| C-02 | Rehash отклонён; fail-closed upgrade в DF3-005 |
| C-03 | Scaffolding принят; `validate` уже существует; DF3-005 |
| B-04, SEC-04 | Приняты с Core-derived paths; DF3-006 |
| C-06 | Не дефект Linux CI; clean-checkout проверка в DF3-009 |
| F-05 | Принят как чистый breaking contract v3 без compatibility layer; DF3-008 |
| F-06 | Переформулирован как taxonomy drift; DF3-007/DF3-009 |
| B-06 | Отклонён: halt уже versioned через contract `$id` |
| B-07 | Отложен до профилирования FuseMap refresh |
| C-05, F-08 | Приняты как docs/config validation; DF3-009 |

## Правила исполнения

- Одна карточка — один reviewable commit или короткая последовательность связанных commits.
- Сначала Red/adversarial acceptance, затем implementation и Green.
- При изменении контракта синхронно обновлять docs, skills, schemas, templates, installers, validators и tests.
- Для каждой карточки проверять влияние на размер Worker packet; security metadata не должна раздувать prompt.
- После каждой карточки запускать `tests/smoke-test.ps1`, `tests/smoke-test.sh`, pytest и layout validation на изолированном продукте.
- Не делать `git push`, merge, auto-accept или автоматический re-stamp evidence.
- Очередь и следующий шаг всегда отражать в `backlog/product/index.md`.

## Definition of Done 3.0

- Gate нельзя закрыть ручной сменой status или поддельным evidence YAML.
- CI leash проверяет PR/push range, а не пустой worktree diff.
- Framework pin покрывает исполняемый Core и runtime assets.
- Docs/code/ops routes проходят полный lifecycle и archive.
- Wheel проходит установку и полный smoke в чистом окружении.
- Human Gate receipt проверяется согласно integrity profile.
- v3 installation не принимает artifacts неподдерживаемой версии как действующие contracts и выдаёт точную blocking diagnostic вместо неявной совместимости.
- Bench включает adversarial Worker и не награждает gate spam.
- Три чистых v3-прогона каждого release case на reference 35B A3B profile помещаются в 32k; каждый прогон и медианные метрики достигают абсолютных thresholds из DF3-001.
