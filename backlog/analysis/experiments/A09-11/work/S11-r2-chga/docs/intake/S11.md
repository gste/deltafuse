# Evaluator intake CHG-A

Добавить optional burst_allowance при инициализации TokenBucketLimiter.
Пока ключ не исчерпал burst_allowance дополнительных токенов, rejected consume
должен один раз получить extra tokens и повторить попытку в том же вызове.
burst_allowance по умолчанию 0 (поведение без изменений).
