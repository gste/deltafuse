# security.ratelimit

## REQ-RL-01 Capacity and refill
TokenBucketLimiter MUST initialize with capacity > 0 and refill_rate >= 0 (скорость пополнения).

## REQ-RL-02 Consume
consume(key, tokens) MUST return True and deduct tokens when the key has enough tokens, otherwise False without deduction.

## REQ-RL-03 Unknown keys
An unknown key MUST start at full capacity.

## REQ-RL-04 is_blocked
is_blocked(key) MUST return False for the baseline limiter (no penalty lock).

## Примеры использования

### Инициализация

```python
from ratelimit import TokenBucketLimiter

limiter = TokenBucketLimiter(capacity=10, refill_rate=1)
```

### Потребление с проверкой

```python
if limiter.consume("user:42", tokens=3):
    # proceed with the request
else:
    # reject: not enough tokens
```

### Обработка ValueError

```python
try:
    limiter.consume("user:42", tokens=-1)
except ValueError as exc:
    # tokens must be non-negative
    log.error("invalid token count: %s", exc)
```

## Архитектурные решения

### Выбор алгоритма: Token Bucket

В качестве алгоритма ограничителя выбран Token Bucket (RFC 2697). Обоснование:

- Разрешает кратковременные всплески при накоплении токенов, что соответствует
  реальному поведению клиентов.
- Поддерживает переменную скорость пополнения через `refill_rate`.
- Имеет простую и эффективную реализацию с O(1) операцией `consume`.

Сравнение с Leaky Bucket:

- Leaky Bucket выравнивает поток, отклоняя всплески; Token Bucket их разрешает.
- Для сценариев с допустимой пульсацией запросов Token Bucket предпочтительнее.

Ссылки: RFC 2697 — "HTTP Rate Limiting".
