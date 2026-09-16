# Small-LLM Quality Contract

[**English**](small-llm-contract.md) | [Русский](small-llm-contract.ru.md)

Нормативен для фреймворка (V3-FIX-020). История программы живёт в
`backlog/product/v3/`; этот документ — каноническая спецификация.

## Референсная рамка

- Референсный нижний класс Worker — локальная LLM класса 35B A3B. Первая
  qualification model — `ornith-1.5-35b-a3b` через LM Studio. Cloud или более
  крупная модель не требуются для корректного прохождения Process.
- Полный вызов Worker должен помещаться в context window **32k токенов**
  (qualification window).
- Framework-controlled input по умолчанию ограничен **16 000 токенов и 24
  уникальными файлами** на вызов. Остаток окна — обязательный запас для
  host/system instructions, tool exchange и ответа модели.

## Контракт

- Один вызов Worker решает одну capability, один artifact layer и один
  проверяемый outcome.
- `next` передаёт точные bounded reads; ни один шаг не требует загрузки всего
  репозитория, всего `docs/spec/**` или соседних Changes.
- Core выполняет routing mechanics, transition checks, diff calculation и
  evidence bookkeeping вне prompt модели.
- Receipts, manifests, полные журналы и длинные command outputs не входят в
  Worker context без явной диагностической необходимости; Core отдаёт краткое
  структурированное резюме.
- При превышении token/file бюджета работа декомпозируется. Обрезание
  обязательного контекста и молчаливое продолжение запрещены.
- Качество измеряется disk-based bench: correctness, завершённые stages,
  retries, context tokens, уникальные файлы, выдуманные пути и envelope
  violations.
- Абсолютные численные release thresholds для v3 (T1–T8, для каждого прогона и
  для медиан) зафиксированы в `backlog/product/v3/thresholds.md`; прогоны
  выполняет `scripts/qualify.py`. Ослабление любого порога — отдельный
  maintainer Decision с записью в программу бэклога.
