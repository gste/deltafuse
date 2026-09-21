# Конверт записи (DeltaFuse ↔ leash / хост)

[English](leash.md) | [**Русский**](leash.ru.md)

Машинная схема: [leash.schema.yaml](leash.schema.yaml) (контракт v1).

**Канон продюсера.** `deltafuse leash`, hook или хост пинят ту же схему. Не схема продукта; installer не копирует `docs/contracts/**`.

Продюсер: `deltafuse next --json`. Проверка: `deltafuse leash`. `envelope` — объект по схеме или JSON `null`. `null` — нет готового шага воркера. Код/ops/deploy в таком diff — orphan, `leash` падает. `docs/spec/**` — orphan только после `project.baseline: accepted`. `docs/intake/**` и `AGENTS.md` не orphan.

Intake `write` не содержит `src/**`. Declare/Implement оставляют evidence и `tests/**`, код сужается до `allowed_paths`. Свежий `init` пишет `workflow.leash: off` (без hook). `advisory` — те же нарушения, exit 0. `enforce`/`advisory` ставят локальный `pre-commit` на `deltafuse leash`. Hook не делает `git push`.

При `halt.kind` `decision` или `spec` `envelope` — JSON `null`: product-code write-tools выключены, пока висят кнопки.

**По чему судится diff.** Guard сверяет diff от `--base` (по умолчанию `HEAD`) с готовыми envelope **и** с envelope всех шагов, которые каждый Change прошёл с этой базы, — по receipts переходов. Записи законченного шага не судятся по envelope следующего; halt останавливает новую работу, но не запись уже сделанной. Для Declare/Implement добавляются только задачи, чей файл изменился с базы.

**Журналы ядра (DF3-007).** `.deltafuse/transitions.jsonl`, `gate-journal.jsonl` и `journal-head` проходят только как дописывание в форме ядра: старые строки не тронуты, digest каждого receipt перехода сходится и цепочка воспроизводится, gate-receipts текущего формата с проверенными цепочкой и head. Иначе — нарушение. `.deltafuse/trusted-keys.yaml` в diff воркера не бывает никогда. Digest receipt без ключа: guard доказывает форму записи ядра, а не авторство — это п. 4 роадмапа.

## Хост обязан

| Нужно | Источник | MUST |
|---|---|---|
| Список записи | `envelope.write` | Резать write-tools агента (ApplyPatch, write, edit) этими глобами. Не выдумывать лишние. |
| Пустой envelope + `leash: enforce` | `envelope` JSON `null` | Нет готового шага воркера. Не давать product-глобы (`src/**`, `tests/**`, ops/deploy; `docs/spec/**` после accepted baseline). Ждать / inspect можно. |
| Halt + envelope | `halt.kind` decision\|spec | Envelope пустой. Не открывать запись в код продукта, пока кнопки Human Gate на экране. |
| Хост не режет tools | `/run` | Всё равно звать `deltafuse leash` перед концом шага. Это не замена git hook. |
| Доска / кнопки | Другой репозиторий | UI fuse-map и кнопки Cursor **вне** `src/deltafuse/**`. Этот репозиторий UI не содержит. |

Хост не включает write-tools вне `envelope.write`, не считает null envelope «пиши куда угодно» при `enforce`, не auto-accept, не кладёт плагин Cursor / доску fuse-map в `src/deltafuse/**`.
