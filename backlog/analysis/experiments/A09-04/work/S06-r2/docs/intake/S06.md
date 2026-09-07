# Запрос пользователя: Добавить аудит-лог и алерты при превышении порогов (S06)

Ниже прикреплён лог работы системы за последние 48 часов. Необходимо проанализировать его и на основании анализа:

1. Реализовать подсистему `monitoring.audit_log`, которая записывает каждое событие consume (key, tokens, result, timestamp) в структурированный лог.
2. Добавить механизм алертов: если за скользящее окно в 60 секунд количество отклонённых запросов по одному ключу превышает порог (по умолчанию 100), генерируется алерт-событие.

Вот типичный лог (фрагмент из 200 строк с дублями, нерелевантными записями и мусором):

```
[2026-09-05T10:00:00Z] INFO  ratelimiter key=api_user_42 action=consume tokens=1 result=ok balance=99
[2026-09-05T10:00:00Z] DEBUG internal_gc cycle=1423 freed=0
[2026-09-05T10:00:01Z] INFO  ratelimiter key=api_user_42 action=consume tokens=1 result=ok balance=98
[2026-09-05T10:00:01Z] INFO  ratelimiter key=api_user_42 action=consume tokens=1 result=ok balance=97
[2026-09-05T10:00:01Z] DEBUG internal_gc cycle=1424 freed=0
[2026-09-05T10:00:02Z] WARN  network retransmit src=10.0.0.5 dst=10.0.0.1 seq=44821
[2026-09-05T10:00:02Z] INFO  ratelimiter key=api_user_42 action=consume tokens=5 result=ok balance=92
[2026-09-05T10:00:03Z] INFO  ratelimiter key=api_user_42 action=consume tokens=1 result=rejected balance=0
[2026-09-05T10:00:03Z] INFO  ratelimiter key=api_user_42 action=consume tokens=1 result=rejected balance=0
[2026-09-05T10:00:03Z] INFO  ratelimiter key=api_user_42 action=consume tokens=1 result=rejected balance=0
[2026-09-05T10:00:04Z] DEBUG internal_gc cycle=1425 freed=12
[2026-09-05T10:00:04Z] WARN  network retransmit src=10.0.0.5 dst=10.0.0.1 seq=44822
[2026-09-05T10:00:05Z] INFO  ratelimiter key=api_user_99 action=consume tokens=1 result=ok balance=49
... (ещё ~185 аналогичных строк с дублями DEBUG/WARN и событиями по 12 ключам)
```

Требования:
- Audit log должен быть append-only и поддерживать ротацию по размеру (макс. 10 МБ на файл).
- Алерт должен содержать: key, window_start, window_end, rejection_count, threshold.
- Нерелевантные строки (DEBUG internal_gc, WARN network) не должны влиять на логику.
