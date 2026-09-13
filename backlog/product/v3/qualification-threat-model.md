# Qualification threat model (QF-004)

- **Статус:** актуален для runner `scripts/qualify.py` + `scripts/qualify_executor.py` (QF-019/QF-020)
- **Scope:** qualification кампании DF3-009 (reference Worker 35B A3B), не
  продукционный runtime DeltaFuse.

## Активы

| Актив | Риск при компрометации |
|---|---|
| Judge pack (`process/bench/cases/**` — oracle, hidden_suite) | Worker читает ответы → фиктивный pass qualification |
| Host filesystem (вне sandbox) | Утечка/порча данных, обход measurement |
| Thresholds (`T1–T8`, `ABSOLUTE`) | Ослабление критериев → недействительный verdict |
| Результаты кампании (`bench/runs/**`) | Подмена reports/manifest задним числом |

## Границы и гарантии

### Release-граница — isolated executor (QF-013, обязателен для release/reference)

1. **Режимы исполнителя** (`scripts/qualify_executor.py`): `isolated` —
   единственный режим, который может дать release-verdict `pass`;
   `local-dev` — только для разработки, его кампании всегда получают
   итоговый verdict `non-release` (cap в runner, schema допускает значение).
2. **Граница (QF-019)**: Worker-фаза (model calls, orchestration, scoring,
   reports) остаётся judge-side; внутрь command-контейнера уходит только
   уже разобранный разрешённый argv. Контейнер получает: run sandbox
   (read/write) и pinned образ (wheel DeltaFuse + pytest + git). Judge pack,
   framework checkout, runner-скрипты и helper-модули **не монтируются** и
   в образ не попадают (каноническая сборка — `scripts/build_qual_image.py`
   только из wheel чистого commit; для release принимается только
   immutable digest-ссылка `sha256:…`).
3. **Единая политика и probe (QF-020)**: command-контейнер запускается с
   `--network none`, read-only rootfs, non-root UID, `--cap-drop ALL`,
   `no-new-privileges`, лимитами memory/pids; temp/home направлены в
   gitignored scratch внутри sandbox. Adversarial probe исполняется В ТОМ ЖЕ
   контейнере до первой и после последней Worker-команды: sentinel (по
   host-пути, уникальному имени и точному content-hash по всем видимым
   корням), имена pack/checkout, записи вне sandbox/scratch, запись rootfs и
   runtime control paths (docker.sock), сетевое обращение, identity
   контейнера. Копия sentinel внутри разрешённого mount — LEAK, а не
   `blocked` (исправленный ложный негатив QF-013). Effective policy
   (mounts, digest, user, caps, rootfs, network) измеряется runtime-inspect
   и сверяется с ожидаемой; declared tag недостаточен.
4. **Attestation** в manifest: executor kind, runtime, image + измеренный
   digest, mounts, network policy, измеренная политика контейнера и отчёты
   probe (before/after, container id) — каждое поле с provenance. Любое
   расхождение блокирует кампанию (`BoundaryViolation` → run/campaign
   blocked, dedicated `boundary_error`).
5. **Fail-closed default**: `--executor isolated` по умолчанию; без
   docker/podman + digest-ссылки `DELTAFUSE_QUAL_IMAGE` кампания завершается
   `PENDING` до первого Worker-вызова.

### L1 — политика runner (local-dev helper, НЕ release-граница)

L1 (argv-политика, staging root, минимальное окружение, inventory-сверка —
см. историю QF-001–QF-008) остаётся включённой только в режиме `local-dev`.
**Ранее этот документ трактовал доступ Worker-authored тестового кода к host
filesystem как приемлемый для release qualification — это утверждение
неверно и удалено (дефект QF-013).** L1 не изолирует: `python -m pytest`
исполняет Worker-код с правами процесса runner, исходный checkout и judge
pack читаемы по абсолютному пути. L1-артефакты не являются release
evidence; verdict `local-dev`-кампании всегда `non-release`.

Ограничение сети Worker-контейнера только LM Studio endpoint на уровне
runtime (firewall/nftables) не гарантируется bridge-сетью; attestation
помечает network policy как declared, и при выполнении QF-018 требуется
либо image-level ограничение, либо зафиксированное исключение.

## Платформенные гарантии

| Угроза | Windows | POSIX |
|---|---|---|
| Запись через junction/symlink | отклонена resolve-guard (`_resolve` → `Path.resolve` → escape) | отклонена аналогично (symlink) |
| Абсолютные/UNC/сетевые пути в argv | отклонены парсером (`\\`, `//`, `X:`) | отклонены (`/`, `//`) |
| `python` из случайного PATH | исключён подстановкой контролируемого интерпретатора | то же |
| Наследование env репозитория | вырезается `StagingRoot.env` | то же |
| Регистронезависимые имена/8.3-алиасы | пути сравниваются через `Path.resolve`; повреждение через алиасы покрыто inventory-diff | n/a |
| Case-insensitive коллизии имён | покрыты inventory (git) | n/a |

## Известные ограничения

- L1 staging не изолирует Worker-код от host filesystem; он допустим только
  в `local-dev` (verdict `non-release`). Release-кампании требуют
  isolated executor (см. Release-граница выше).
- Tamper-guard обнаруживает сдвиг HEAD, но не физическую защиту `.git`;
  физическая защита даётся только release-границей.
- Symmetric: runner сам готовит и убирает staging; конкурентный доступ
  двух кампаний к одному staging-каталогу не поддерживается (base per campaign).
- Worker-контейнер использует bridge-сеть с host-gateway alias до LM
  Studio; полная egress-изоляция до единственного endpoint требует
  image/runtime-level firewall и проверяется при QF-018.
