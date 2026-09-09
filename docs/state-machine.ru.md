# State Machine

DeltaFuse управляет жизненным циклом артефактов через явные машины состояний (State Machines). Состояние фиксируется непосредственно в метаданных каждого артефакта (`change.yaml`, заголовок задачи, frontmatter решения). 

Перемещение файлов по файловой системе **не используется** для кодирования активного состояния процесса. Единственное допустимое перемещение директорий — перенос полностью завершённого и сошедшегося пакета Change в `docs/archive/changes/`.

---

## Project Baseline State

Глобальное состояние проекта определяется в конфигурационном файле `.deltafuse/config.yaml`:

```yaml
project:
  baseline: draft | accepted
```

| Состояние | Описание | Ограничения |
|---|---|---|
| `draft` | Профиль **Bootstrap**: проект находится на этапе первичной инициализации, выделения доменов/возможностей и формирования базовой спецификации. | Продуктовая реализация (код) заблокирована. Разрешены только Intake, анализ и спецификация. |
| `accepted` | Базовая спецификация принята человеком. Проект находится в регулярной разработке. | Разрешён полный цикл разработки Change. Любые доработки и создание новых сервисов идут как Change. |

---

## Change State Machine

Жизненный цикл контейнера изменений (`docs/changes/<change-id>/change.yaml`):

```text
               +-------------------------------------------+
               |                                           |
               v                                           |
[normalized] ---> [analyzing] <---> [blocked-on-decision]  | (Backtracking)
                      |                                    |
                      v                                    |
                 [analyzed]                                |
                      |                                    |
                      v                                    |
           [specification-proposed]                        |
                      |                                    |
                      v                                    |
                  [specified]                              |
                      |                                    |
                      v                                    |
                 [decomposed]                              |
                      |                                    |
                      v                                    |
                  [targeting]                              |
                      |                                    |
                      v                                    |
              [target-confirmed]                           |
                      |                                    |
                      v                                    |
                [implementing]                             |
                      |                                    |
                      v                                    |
                 [implemented]                             |
                      |                                    |
                      v                                    |
                  [verifying] -----------------------------+
                      |
                      v
                 [converged]
                      |
                      v
                 [archived]
```

### Альтернативные терминальные состояния
Change может быть переведён в терминальное состояние на ранних этапах:
- `rejected`: запрос отклонён человеком как нецелесообразный или противоречащий видению продукта;
- `duplicate`: запрос дублирует уже существующий или обрабатываемый Change;
- `not-reproduced`: дефект не подтверждён надёжным Red evidence;
- `superseded`: запрос заменён более широким или реструктурированным Change.

### Таблица переходов Change

| Исходное состояние | Целевое состояние | Событие / Условие перехода | Gate |
|---|---|---|---|
| *none* | `normalized` | Завершён `/intake`. Создан `request.md` с claim IDs `CR-*`. | Каждое утверждение пользователя представлено claim либо исключено. |
| `normalized` | `analyzing` | Начало шага `/analyze-change`. Маршрутизация claims по capabilities. | Существует каталог capabilities (или создаётся в Bootstrap). |
| `analyzing` | `blocked-on-decision` | Обнаружена развилка, требующая Decision Record со статусом `proposed`. | Создан документ `docs/decisions/DEC-NNNN-*.md`. |
| `blocked-on-decision` | `analyzing` | Все блокирующие решения переведены человеком в `accepted` или `rejected`. | Human Gate: нет открытых блокирующих Decisions. |
| `analyzing` | `analyzed` | Завершён анализ всех слайсов, вычислены дельты, проведено глобальное согласование. `workflow.call_width` может разнести записи, но комплект тот же. | На диске есть `routing.yaml`, `slices/` и `coverage.yaml`; все claims покрыты; дельты типизированы. |
| `analyzed` | `specification-proposed` | Требуется изменение спецификации (`requirement_delta: modify/add`). | Сформирован проект правок в `docs/spec/**` и `spec-delta.md`. |
| `analyzed` | `specified` | Изменение спецификации не требуется (`requirement_delta: none`). | Доказано точными ссылками на существующие требования `REQ-*`. |
| `specification-proposed` | `specified` | Правки в спецификации согласованы и смерджены. | Human Gate: утверждённые правки в `docs/spec/**`. |
| `specified` | `decomposed` | Завершён `/decompose-change`. Созданы атомарные задачи `TASK-NNN`. | Все требования слайсов покрыты задачами с явным Test Oracle. |
| `decomposed` | `targeting` | Выбрана задача для реализации, запущен `/target-task`. | Предшествующие зависимые задачи выполнены. |
| `targeting` | `target-confirmed` | Тестовый таргет упал строго по ожидаемой поведенческой причине. | Записан `evidence/red/evidence.yaml`, код продукта не изменён. |
| `target-confirmed` | `implementing` | Запущен `/implement-task`. Начато изменение продуктового кода. | Скоуп файлов ограничен контрактом задачи. |
| `implementing` | `implemented` | Тестовый таргет стал Green, scoped regressions прошли успешно. | Записан `evidence/green/evidence.yaml`. |
| `implemented` | `verifying` | Все задачи пакета Change переведены в состояние `implemented`. | Нет незавершённых или зависших задач. |
| `verifying` | `converged` | Запущен `/verify-change`. Доказана сквозная трассируемость и сходимость всех слоёв. | Все объявленные дельты применены, тесты зелёные, расхождений нет. |
| `verifying` | `analyzing` | Обнаружен пропуск в спецификации, архитектурный зазор или скоуп-дрифт. | **Escalation Gate**: возврат на анализ без несанкционированных правок. |
| `verifying` | `not-reproduced` | Закрытие Change как невоспроизведённого дефекта или подтверждённого no-op. | В `verification.md` зафиксирован исход `not-reproduced`. |
| `analyzing` / `targeting` | `not-reproduced` | Дефект не воспроизводится на кодовой базе; Red-тест не выявил ожидаемого сбоя. | Зафиксирован диагностический отчёт или evidence со статусом `result: not-reproduced`. |
| `normalized` / `analyzing` | `rejected` | Запрос нереализуем или отвергнут по результатам маршрутизации/анализа. | Обоснование отказа задокументировано в `analysis.md`. |
| `normalized` / `analyzing` | `duplicate` | Запрос дублирует уже существующий активный или архивный Change. | Ссылка на оригинальный `CHG-*` зафиксирована в `change.yaml`. |
| `analyzing` | `superseded` | Change заменён более широким или реструктурированным запросом. | Ссылка на замещающий Change зафиксирована в `change.yaml`. |
| `converged` | `archived` | Пакет Change целиком перемещён в `docs/archive/changes/<date>-<change-id>/`. | Change удалён из активных списков, история неизменна. |

---

## Slice State Machine

Слайсы (`slices/SLICE-NN.md`) управляют параллельным или независимым анализом крупных частей Change:

```text
draft -> analyzing -> blocked -> analyzed -> specified -> decomposed -> verified
```

- `draft`: слайс выделен на этапе маршрутизации;
- `analyzing`: читаются релевантные модули спецификации, формируется дельта;
- `blocked`: слайс ожидает разрешения зависимого Decision или соседнего слайса;
- `analyzed`: дельта слайса полностью типизирована;
- `specified`: нормативная база слайса зафиксирована в спецификации;
- `decomposed`: сформированы задачи по реализации слайса;
- `verified`: все задачи слайса завершены и проверены.

---

## Task State Machine

Состояния отдельных атомарных задач (`tasks/TASK-NNN-<slug>.md`):

```text
               +-----------------------------+
               |                             |
               v                             |
[pending] ---> [targeting] ---> [target-confirmed] ---> [implementing] ---> [implemented] ---> [verified]
  |               |
  |               +------------> [blocked]
  |
  +----------------------------> [cancelled / superseded]
```

- `pending`: задача создана, ожидает выполнения зависимостей;
- `targeting`: пишется минимальный тест, доказывающий Red;
- `target-confirmed`: зафиксирован воспроизводимый Red evidence;
- `implementing`: пишется минимальный продуктовый код;
- `implemented`: тест и регрессии прошли успешно (Green evidence);
- `verified`: сходимость задачи подтверждена в ходе общей верификации Change;
- `blocked`: обнаружено внешнее препятствие или ошибка в контракте;
- `cancelled`: задача отменена по решению архитектора/разработчика;
- `superseded`: заменена другой задачей.

Задачи не удаляются после выполнения. Они сохраняются в пакете Change для сохранения полной истории и трассируемости.

---

## Decision State Machine

Состояния решений в реестре `docs/decisions/DEC-NNNN-*.md` (решения могут быть привязаны к Change через `change: CHG-NNN` либо создаваться на уровне репозитория/Bootstrap с `change: null`):

```text
[proposed] ---> [accepted]
           ---> [rejected]
           ---> [superseded]
```

- `proposed`: черновик решения сформирован аналитиком или ИИ, содержит варианты (options) и контекст;
- `accepted`: решение принято человеком (Human Gate); последствия зеркалируются в `docs/spec/**`;
- `rejected`: решение отклонено человеком, выбран альтернативный путь или сохранён статус-кво;
- `superseded`: решение устарело и заменено более новым принятым решением.

ИИ строго запрещено переводить Decision в статус `accepted` или `rejected`.

---

## Evidence State Machine

Фазы доказательной базы (`evidence.schema.yaml`):

```text
[none] ---> [red] ---> [green]
             \          /
         [regression]  /
              \       /
            [verification]
```

- `red`: таргетный тест падает на исходном коде по строго ожидаемой причине (`evidence/red/<task-id>.yaml`, обязательное поле `task: TASK-NNN`);
- `green`: таргетный тест и регрессионный набор проходят успешно (`evidence/green/<task-id>.yaml`, обязательное поле `task: TASK-NNN`);
- `regression`: выделенный отчёт о запуске регрессионного набора тестов (`evidence/regression/<task-id>.yaml`, обязательное поле `task: TASK-NNN`);
- `verification`: Change-level автоматизированный верификационный прогон перед архивацией (`evidence/verification/run.yaml`, поле `task: null`, так как относится ко всему Change).

---

## Инвариант версионирования (Framework & Schema Pinning)

При нормализации Change в `change.yaml` фиксируются:
```yaml
schema_version: 2
framework:
  version: 2.0.0
  content_hash: sha256:...
```

Активный Change обязан завершаться в соответствии с зафиксированной версией фреймворка. Обновление внешнего DeltaFuse фреймворка не меняет семантику активных Changes автоматически; миграция активных процессов требует явной процедуры.
