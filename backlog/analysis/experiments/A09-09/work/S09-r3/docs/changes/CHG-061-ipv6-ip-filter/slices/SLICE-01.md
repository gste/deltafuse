---
id: SLICE-01
change: CHG-061-ipv6-ip-filter
title: Обоснованное закрытие запроса поддержки IPv6
status: analyzed
primary_capability: change_management
related_capabilities:
  - security.ip_filter
  - infrastructure.network
policies: []
spec_refs:
  - docs/spec/security/ip_filter.md
claims:
  - CR-001
  - CR-002
  - CR-003
  - CR-004
  - CR-005
  - CR-006
depends_on: []
---

## Slice analysis

### intent
Запрос CHG-061 не реализуем в текущем окружении: он дублирует отклонённую CHG-042, замещён CHG-060 и опирается на неоткрытую инфраструктуру (INFRA-789, IPv6-стенд отключён). Требуется обоснованное закрытие с provenance.

### delta_kind
none — нормативные изменения в spec отсутствуют; `security.ip_filter` явно фиксирует IPv6 как out of scope.

### requirement_delta
none. REQ-IP-01 уже исключает IPv6 из охвата; запрос не добавляет нового требования.

### design_impact
none. Изменений архитектуры, каталога способностей или решений не требуется.

### risk
low. Единственный риск — потеря provenance при закрытии; устраняется фиксацией ссылок на CHG-042, CHG-055, CHG-060, INFRA-789.

### size
small.

### out of scope
Реализация IPv6, обновление сетевого стека (INFRA-789), нормативные правки spec.

### unchanged behavior
IpFilter принимает только IPv4; IPv6 остаётся за пределами охвата до апгреда сетевого стека.

### context budget
max_tokens: 2000, max_files: 6.

### unknowns
Точная дата и автор решения по CHG-042; прямая связь CHG-060 с текущим `security.ip_filter`. Не являются блокирующими решениями для данного запроса.
