# Запрос пользователя: Добавить распределённый Rate Limiter с Redis-бэкендом (S07)

В продукте уже существуют 15 capabilities в каталоге `docs/spec/_capabilities.yaml`:

```yaml
capabilities:
  - security.ratelimit
  - security.auth_tokens
  - security.ip_filter
  - monitoring.usage_stats
  - monitoring.audit_log
  - monitoring.health_check
  - billing.metering
  - billing.invoices
  - billing.payment_gateway
  - api.versioning
  - api.rate_headers
  - api.pagination
  - infra.config_reload
  - infra.feature_flags
  - infra.circuit_breaker
```

Необходимо добавить новую capability `infra.distributed_ratelimit` — распределённый Rate Limiter с Redis-бэкендом:

1. Должен поддерживать все операции исходного `security.ratelimit` (init, consume, get_stats), но с хранением состояния в Redis вместо in-memory.
2. Атомарные операции через Lua-скрипты в Redis для гарантии консистентности при конкурентном доступе из нескольких инстансов.
3. Конфигурируемое переключение между in-memory и distributed бэкендами через `infra.config_reload`.
4. TTL для ключей в Redis, равный `capacity / refill_rate * 2` секунд.
5. Graceful degradation: при недоступности Redis автоматически переключаться на in-memory с логированием предупреждения.
6. Health check endpoint через `monitoring.health_check` для проверки связности с Redis.

Эта capability значительно крупнее остальных — ожидается ~500 строк кода, 3 файла спецификации и отдельный integration test suite.
