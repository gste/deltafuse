---
change: CHG-061-ipv6-ip-filter
status: superseded
slices:
  - SLICE-01
---

# spec-delta — CHG-061-ipv6-ip-filter

### none

Нормативные изменения в спецификацию отсутствуют. `requirement_delta: none`.

`security.ip_filter` уже фиксирует IPv6 как out of scope:

> REQ-IP-01 — IpFilter MUST accept IPv4 addresses. IPv6 is out of scope until the network stack is upgraded.

Запрос CHG-061 не добавляет нового требования и не изменяет наблюдаемое поведение capability. Изменения в `docs/spec/**` не требуются.

### Provenance

- CHG-042 — отклонена (rejected) архитектурным комитетом (request.md, CR-002).
- INFRA-789 — обновление сетевого стека, статус not-started (request.md, CR-003).
- CHG-055 — аналогичная функциональность, замещена (superseded) задачей CHG-060 (request.md, CR-004).
- CHG-060 — полная переработка ip_filter с поддержкой CIDR-нотации.

### spec_refs

- docs/spec/security/ip_filter.md — REQ-IP-01 (IPv6 out of scope), доказывает достаточность текущей спецификации.
