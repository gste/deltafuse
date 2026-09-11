# Железный поводок

Программа очереди **LS-***. Не lifecycle продукта и не замена `docs/**`.

Воркер (в том числе фронтир) в Cursor может не вызвать `next` / `check-gate` и править `src/` из чата. Skills и markdown это не удерживают. Поводок — не «модель честная», а машина, которая **отказывает**, если процесс обошли.

## Что считаем поводком

1. Ядро называет текущий **write envelope** (глобы шага + `allowed_paths` задачи).
2. `deltafuse leash` сверяет diff с envelope и ловит правки продукта без Change.
3. Git hook / CI в consuming repo вызывают `leash` (не честное слово воркера).
4. `accepted` / `rejected` на DEC и spec пишет только `deltafuse decide`.
5. Evidence YAML без штампа ядра не закрывает Declare/Implement.
6. Хост режет write-tools по envelope и не даёт воркеру выбрать Halt. Кнопки Cursor и UI fuse-map — не этот репозиторий.

## Что не делаем

- Песочница LLM внутри `src/deltafuse/**`.
- Auto-accept, merge, `git push` из Core.
- Плагин Cursor / MCP-кнопки в этом репо.
- Второй процесс (Spec Kit, OpenSpec, `.kiro`) рядом с каноном.
- Восстанавливать `backlog/analysis/experiments/**`.

## Конфиг продукта

`workflow.leash`: `off` | `advisory` | `enforce`. Свежий `init` — `off` (MVP в чате). Когда `project.baseline: accepted` — включать `enforce`. per-ankh и fuse-map должны включить, не ждать дефолта.
