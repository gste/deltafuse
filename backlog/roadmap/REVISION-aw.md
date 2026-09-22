# Ревизия: schema-driven-artifact-writer

Основание — политика из `backlog/README.md`: «Здесь находится только живая
очередь работ. Завершённые задачи сохраняются в истории Git.»

## Состояние

`queue.json`: **47 карточек из 49 закрыты**, статус очереди `in_progress`.

Открыты две: **AW-20** (Close acceptance and publish migration/handoff) и
**AW-42** (Reconcile final source identity, test coverage and acceptance
evidence).

**Обе — про закрытие, а не про функциональность.** Вся реализация, схемы, тесты
и сверки завершены; по `RESULT.md` из одиннадцати критериев приёмки девять
`Satisfied`, два открыты.

### Открытый цикл, а не открытая работа

Поле `work` карточки AW-20 содержит, в обратном порядке:

- «Fifth-review reopening…»
- «Reopened after third review…»
- «Reopened after second review…»
- «Reopened after review…»

В каталоге лежат `REVIEW.md`, `REVIEW-2` … `REVIEW-6`, `PLAN-REVIEW.md`,
`RECONCILIATION-CHECKLIST.md`. В `queue.json` — `review_snapshot`,
`second_review_snapshot`, `third_review_snapshot`, `fourth_review_snapshot`.

Каждое переоткрытие требовало сверить предыдущие сверки. Это не незавершённая
задача — это **незавершающийся контур**. Он не закроется добавлением шестого
ревью.

## Два настоящих блокера внутри

Под пятью слоями сверки лежат ровно два непройденных факта:

| блокер | источник | куда переносится |
|---|---|---|
| POSIX-раннер недоступен; wheel-квалификация пройдена только на Windows | AW-41, `RESULT.md`: `Satisfied on Windows / Wheel (POSIX Runner Open Blocker)` | [q0 / 0.3](q0-qualification-baseline/README.md) |
| Живого прогона малой модели не было; протокол есть, исполнения нет | AW-40 / AW-20, `RESULT.md`: `Satisfied Protocol (open_for_AW-20 without synthetic claims)` | [q0 / 0.4](q0-qualification-baseline/README.md) |

Второй блокер — **не хвост, а шов в новую работу**: живой прогон малой модели и
есть первая строка будущей таблицы бенчмарка. В старом бэклоге он висел как
недоделка, в роадмапе он становится целью пункта 0.

## Рекомендация

**Закрыть эпик явным решением, а не шестым ревью.**

1. Записать в `RESULT.md` честный финальный статус: 47/49 закрыты, тесты зелёные,
   wheel квалифицирован на Windows, два блокера перенесены в roadmap q0 с
   указанием карточек-источников.
2. Перевести `queue.json` → `status: "closed"`, AW-20 и AW-42 → `superseded` со
   ссылкой на `backlog/roadmap/q0-qualification-baseline/README.md`.
3. Удалить каталог. История остаётся в Git — это и есть политика из
   `backlog/README.md`.
4. Убрать пункт из `backlog/README.md`, поставить вместо него roadmap.

Шаги 1–2 стоят полчаса и оставляют в истории читаемый след. Шаг 3 без них
потеряет контекст, поэтому порядок важен.

## Команда удаления — не выполнена

Каталог не удалён: 308 файлов, все отслеживаются Git. Решение за владельцем.
После шагов 1–2:

```bash
git rm -r backlog/schema-driven-artifact-writer
```

Восстанавливается из истории в любой момент:

```bash
git checkout <commit-до-удаления> -- backlog/schema-driven-artifact-writer
```

## Что переносить не надо

Оценочные материалы (`evaluation/`, 65 файлов) — это следы прогонов под
протокол AW-40, привязанные к версии фреймворка 3.1.0 и к конкретной модели.
Референсный класс сменился с A3B на dense 35–70B, пороги T1–T8 пишутся заново.
Эти данные к новому замеру неприменимы и переносу не подлежат — но именно они
показывают, что протокол исполним, и ссылку на них стоит сохранить в
`RESULT.md` перед удалением.
