# Ядро и воркер

[English](core-and-worker.md) | [**Русский**](core-and-worker.ru.md)

**Процесс** — lifecycle, по которому мы работаем (`Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`). Он описан в [workflow.ru.md](./workflow.ru.md). Процесс — не runtime-роль.

На этом Процессе две runtime-роли. Их нельзя смешивать.

| Имя | English | Что это | Чем это не является |
|---|---|---|---|
| **Ядро** | Core | Машина, которая исполняет Процесс: FSM, гейты, evidence, `next`, archive, `board` | LLM. Человек, который заполняет файлы Change. Описание Процесса |
| **Воркер** | Worker | LLM **или** человек, который пишет артефакты Change текущего шага | CI/OS-джоба. Очередь работы. Human Gate. Тот, кто выбирает следующий шаг или классифицирует Red/Green |

Ядро — kernel CLI: `deltafuse next`, `evidence`, `check-gate`, `archive`, `board`. Оно читает git продукта. Оно не выдумывает claims, текст спецификации, TASK и код продукта. Оно не вызывает модель.

Воркер читает то, что разрешает шаг, и пишет только файлы этого шага. Одни и те же пути для LLM и человека. Skills (`process/skills/*/SKILL.md`) привязывают воркера к LLM. `deltafuse next --human` привязывает тот же шаг к человеку. Второго процесса «для людей» нет.

```text
Воркер  --только файлы Change-->  git продукта
Ядро    --next / evidence / check-gate / archive-->  git продукта
Ядро    --halt, если гейт не прошёл-->  Воркер
```

## Почему Worker — не CI worker

В этом репозитории **Worker / воркер** всегда значит исполнитель шага (`llm | human`). Это не:

- джоба GitHub Actions / очереди;
- OS worker process;
- производная очередь (`deltafuse next --list`) — её считает Ядро;
- **Human Gate**.

Если речь про джобы, очереди или merge — не говорите Worker.

## Human Gate — не воркер

**Human Gate** (DEC / accept spec / merge) — остановка в Процессе. Пройти её может только человек. Заполнить `/analyze` или `/declare` вручную — работа воркера. Принять `DEC-*` — работа Gate. Один человек, две шляпы. Ядро не auto-accept Gate. Воркер не выдаёт Gate за шаг.

## Сквозной режим

Точка входа LLM-воркера по умолчанию — `/run`. Воркер вызывает `deltafuse next`, загружает названный skill и продолжает в той же сессии. Человек не вставляет каждую slash-команду.

Цикл останавливается только когда:

1. `halt.kind` = `decision` — показать `halt.choices`, ждать, затем `deltafuse decide --decision …`.
2. `halt.kind` = `spec` — показать `halt.choices`, ждать, затем `deltafuse decide --spec …`.
3. Гейт упал, задача blocked, или человек выбрал inspect — стоп, осмотр, затем снова `/run` или названный шаг.

Список кнопок хоста — [контракт halt](./contracts/halt.ru.md). `deltafuse decide` записывает клик, это не auto-accept. Ядро UI не рисует. Merge и `git push` остаются Human Gate. Список записи — [конверт](./contracts/leash.ru.md) (`deltafuse leash`). fuse-map живёт в другом репозитории и читает [снимок доски](./contracts/board-snapshot.ru.md).

Одношаговые slash-команды остаются, чтобы после сбоя перезапустить один шаг.
