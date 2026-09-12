# DeltaFuse 3.0 — decision records

Canonical v3 decision records. Каждый DR сформулирован до implementation-коммитов
реализации v3 и меняется только отдельным maintainer Decision. Исходный аудит
и завершённые карточки сохранены в Git history. Текущее состояние программы —
в [deltafuse-3](../deltafuse-3.md).

## DR-3.0-1 — Transition authority (Core-owned transitions)

- **Статус:** accepted (2026-09-12)
- **Влияет на:** DF3-004, DF3-006, DF3-007, DF3-008
- **Red-тесты:** `tests/unit/test_v3_red_acceptance.py` (F-01, F-03, F-04, SEC-03, SEC-04)

**Decision.** В v3 единственным авторитетом lifecycle-переходов является Core.
Worker пишет содержательные Change-артефакты; статусные поля (`change.yaml` status,
task status, evidence-статусы) меняет только Core-команда перехода по результату
валидации gate. Ручная правка статусного поля не является переходом: Core
перечитывает журнал переходов (transition journal) и принимает только те статусы,
у которых есть валидируемый Core receipt.

**Обоснование.** Аудит показал три класса обходов, все через статусные поля,
которые сегодня пишет Worker: archive bypass через ручной `status: converged`
(F-01), deadlock через незакрытый `specification-proposed` (F-03) и бесконечный
re-Analyze (F-04). Пока Worker владеет статусами, каждый gate — optional
decorator над честным файлом.

**Consequences.** `check-gate` и `next` остаются read-only; переход выполняет
отдельная Core-команда (решение 10 плана). Red/Green остаются evidence states:
Core штампует evidence-файлы, Worker их не переписывает.

## DR-3.0-2 — Distribution (wheel + immutable runtime bundle)

- **Статус:** accepted (2026-09-12)
- **Влияет на:** DF3-003, DF3-005
- **Red-тесты:** `tests/unit/test_v3_red_acceptance.py` (B-01, SEC-02)

**Decision.** Официальные каналы установки v3 — nested source checkout и wheel.
Wheel содержит runtime bundle (schemas, templates, сгенерированные при build
ассеты), immutable по содержимому и покрытый framework manifest/hash.
`pyproject.toml` обязан поставлять `process/schemas/**` и `process/templates/**`;
manifest обязан покрывать `src/deltafuse/**`. `docs/**` в продукт не копируется.

**Обоснование.** B-01: установленная wheel нефункциональна (`SchemaRegistry`
падает на старте). SEC-02: lock-хеш не видит подмену Core-кода. Оба дефекта
следуют из того, что пакетные границы не совпадают с границами доверия.

**Consequences.** CI должен строить и устанавливать wheel в чистом окружении
(перенос теста сборки — в DF3-003/DF3-005). `deltafuse new` scaffolding
использует шаблоны из пакета, а не из продуктового дерева (DF3-005).

## DR-3.0-3 — Integrity profiles (local vs signed host broker)

- **Статус:** accepted (2026-09-12)
- **Влияет на:** DF3-007, DF3-004
- **Red-тесты:** `tests/unit/test_v3_red_acceptance.py` (SEC-03)

**Decision.** v3 определяет два integrity profile для Human Gate receipts:

1. `local` — локальный hash chain; защищает только от случайной порчи.
   Работает без host broker; честно не заявляет защиту от подделки.
2. `signed` — receipts подписывает доверенный host broker ключом, находящимся
   вне Worker write/read surface. Core проверяет подпись при валидации gate.

CLI всегда работает в одном из профилей и не должен silent-fallback переходить
между ними. Contracts не обещают защиту от полностью скомпрометированной OS,
Python environment или maintainer account — это вне границы доверия.

**Обоснование.** SEC-03/SEC-05: плоский JSONL-журнал и leash-исключения
`.deltafuse/**` позволяют Worker дописывать human clicks. Hash chain не лечит
adversarial Worker (он может пересчитать chain); лечит только вынос signing key
за пределы Worker-поверхности.

**Consequences.** Формат receipts и подписи — контракт DF3-007; валидация по
профилю — в `check-gate`. Leash-исключение журнала убирается в DF3-004/DF3-007.
