# DeltaFuse 3.0 — qualification host contract (measurement host / tokenizer)

- **Статус:** принят (QF-022, 2026-09-13; правила перенесены из
  [thresholds.md](thresholds.md), где оставался непредрешённый численный
  допуск `+48` из QF-015 — удалён этим же пакетом)
- **Scope:** measurement-хост квалификационных кампаний DF3-009
  (LM Studio, `ornith-1.5-35b-a3b`). Численные пороги качества T1–T8 —
  только в [thresholds.md](thresholds.md).

## Референсный host

| Параметр | Требование |
|---|---|
| Host | LM Studio, OpenAI-совместимый endpoint, локальный |
| Endpoint | `HOST_BASE_URL` (единственный транспорт runner) |
| Модель | `ornith-1.5-35b-a3b`, загружена до первого Worker-вызова |
| Context window | измеренный (`GET /api/v0/models max_context_length`) ≥ 32768 |
| Cloud fallback | запрещён; runner строит единственный локальный endpoint |

## Tokenizer (QF-015, без численных допусков)

1. Release-verdict `pass` возможен только при **измеренном** полном input
   usage (`usage.prompt_tokens` каждого вызова) и **измеренном**
   framework-controlled input (`POST /api/v0/tokenize`). Состояния
   измерения: `measured` (`host-tokenize`), `estimated-nonrelease`
   (локальная диагностика `chars // 4`, никогда не даёт pass),
   `unavailable`, `error`.
2. Отсутствие tokenize endpoint (404/connection/timeout), garbage-ответ,
   отрицательное или булево число токенов блокируют кампанию (`PENDING`)
   до первого Worker-вызова.
3. Калибровка: фиксированный `CALIBRATION_TEXT`; fingerprint — sha256
   списка token id; проверяется до и после кампании, расхождение обнуляет
   verdict.
4. **Consistency без допуска (QF-022):** `usage.prompt_tokens`
   диагностической completion на калибровочном тексте обязан быть
   измеренным целым и не может быть ниже счёта токенизатора — chat-шаблон
   только добавляет токены. Численный диапазон/допуск (например, `+48`)
   является изменением release gate и требует maintainer Decision в
   [decisions.md](decisions.md), записанного ДО implementation (Human Gate:
   собрать evidence на reference host → предложить диапазон → Decision →
   только потом код).

## Governance

- Любое изменение численного порога/правила этого контракта или
  thresholds.md — maintainer Decision до implementation.
- Revision thresholds.md (git hash-object, попадает в каждый manifest)
  должен быть покрыт accepted Decision — иначе release tooling
  (`scripts/qualify.py --executor isolated`,
  `scripts/threshold_governance.py`) блокирует кампанию.
