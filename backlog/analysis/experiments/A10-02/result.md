# Результат эксперимента A10-02

- **ID карточки:** A10-02
- **Ревизия старта:** `e0108f4`
- **Статус исполнения:** **done**
- **Критерии:** `SPEC-001`, `SPEC-002`, `SPEC-005`, `PROC-002`, `PROC-006`
- **Вердикт:** **pass** — пять кандидатов сведены: один новый LLM-изолят (frozen 1-slice extra), остальное из A09/A10-01 или обоснованный not-tested. Отключение гейтов не принято как удешевление. Skills не патчили.

## Ожидаемое

Typed delta, routing, summary, metadata, human gate — по одному фактору в копии. Для каждого: предотвращённый дефект, цена, решение или not-tested.

Пакетный путь `analysis/matrices/contracts.md` отсутствует; кандидаты из [backlog/matrices/contracts.md](../../matrices/contracts.md) (SPC-01/06, ANA-01/02). В `protocol.md` секции «сравнение» нет — метод из плана A10.

## Наблюдаемое

Таблица: [ablation.md](../../matrices/ablation.md).

**AB-02 (новый прогон):** S05 r2, extra «только SLICE-01» заменён в памяти процесса. Prompt содержит «one or two slice files». На диске SLICE-01 и SLICE-02. Specify `gate ok` (F-010): нет `docs/spec/monitoring/usage_stats.md` / `rate_policy.md`. r1 intake fail (YAML) — шум.

Логи: [runs/S05/r2-ablate-slices/](runs/S05/r2-ablate-slices/).

## Ограничения

n=1 на новом изоляте. Не тюнинг A09. Не ablation канонического `fsm.py`.

## Handoff

- **Готово A10-02:** `done` / `pass`. Дальше [A11-01](../../packets/A11-01.md) (Spec Kit, без LLM).
- A12: усилить `specified` (F-010); extra slices не хардкодить в 1 файл; `analysis.md` optional.
- Skills / integrity не патчить.
