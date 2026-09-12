# DeltaFuse 3.0 — contract matrix

v3-контракты артефактов и то, кто какой инвариант проверяет. Никакой реализации
Завершённые implementation-карточки сохранены в Git history; строки матрицы
остаются обязательствами действующей реализации и release qualification.
Терминология и lifecycle — как в [deltafuse-3](../deltafuse-3.md).

Колонки:

- **Owner** — кто держит проверку в v3: `Core` (kernel, всегда), `Host` (CLI/IDE
  broker, который выдаёт Worker read/write/command capabilities), `CI` (PR/push range).
- **Threat** — класс: `accidental` (ошибочный Worker, гоняется за быстрым
  feedback), `adversarial` (Worker целенаправленно обходит границы). Инвариант
  класса accidental может опираться на подсказки; класса adversarial — только на
  механику, которую Worker не может обойти имеющимися capabilities.

## Матрица

| Контракт | v3-обязательство | Owner | Threat | Красный тест / карточка |
|---|---|---|---|---|
| config (`.deltafuse/config.yaml`) | валидная схема; `workflow.leash` mode; baseline; не редактируется Worker-поверхностью | Core | accidental | LS-004/LS-005 тесты; DF3-008 |
| lock (`.deltafuse/lock.yaml`) | manifest покрывает executable Core + runtime assets (`src/deltafuse/**`), а не только docs/process/scripts/tests | Core + CI | adversarial | B-01/SEC-02 red; DF3-003, DF3-005 |
| Change (`docs/changes/<id>/**`) | статусные поля пишет только Core; ручной `status: converged` не даёт archive bypass | Core | adversarial | F-01 red; DF3-002, DF3-004 |
| Change routing | `route: docs/ops` достигает converged без продуктовых regression-требований | Core | accidental | F-02 red; DF3-002 |
| Evidence (`evidence/<phase>/*.yaml`) | stamp только от Core-команды; команда обязана соответствовать configured test runner; синтетические `python -c` не authentic | Core | adversarial | B-04 red; DF3-006 |
| Gate journal | journal вне Worker write surface; запись Worker'ом = leash violation; в `signed` profile — подписанные receipts | Host + Core | adversarial | SEC-03 red; DF3-004, DF3-007 |
| Task envelope | `allowed_paths` задачи — строгое подмножество slice `target_paths`; расширение = hard FSM error, не merge | Core | adversarial | SEC-04 red; DF3-006 |
| Receipts (v3) | каждый переход выдаёт проверяемый receipt (manifest `hash`/`signature` по integrity profile); нет receipt — статус не принят | Core (+Host в signed) | adversarial | DF3-007 |
| Adapters (`next --json`, leash, halt, board) | envelope/halt/board форматы v3 не содержат security metadata, раздувающей Worker packet; никаких breaking-алиасов v2 | Core | accidental | существующие contract-тесты; DF3-008 |

## Кто что проверяет (итог)

- **Core** — все gate/transition/evidence/envelope инварианты выше; `check-gate`
  и `next` read-only.
- **Host** — физически режет write-tools и команды Worker до envelope и
  configured runner (LS-007); предоставляет broker-подпись в `signed` profile.
- **CI** — diff против PR/push range, а не пустого worktree (SEC-01 → DF3-003);
  сборка wheel в чистом окружении; framework manifest/hash против base.

## Запреты

- Contracts не обещают защиту от полностью скомпрометированной OS, Python
  environment или maintainer account (см. threat model в [deltafuse-3](../deltafuse-3.md)).
- Никакой совместимости с артефактами v2: чужая версия = blocking diagnostic (DF3-008).
- Security metadata (receipts, manifests) не входят в Worker prompt; Core отдаёт
  краткое резюме (Small-LLM Quality Contract).
