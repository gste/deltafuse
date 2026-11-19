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
                  [declaring]                              |
                      |                                    |
                      v                                    |
                  [declared]                               |
                      |                                    |
                      v                                    |
                [implementing]                             |
                      |                                    |
                      v                                    |
                 [implemented] ----------------------------+
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
| `normalized` | `analyzing` | Начало шага `/analyze`. Маршрутизация claims по capabilities. | Существует каталог capabilities (или создаётся в Bootstrap). |
| `analyzing` | `blocked-on-decision` | Обнаружена развилка, требующая Decision Record со статусом `proposed`. | Создан документ `docs/decisions/DEC-NNNN-*.md`. |
| `blocked-on-decision` | `analyzing` | Все блокирующие решения переведены человеком в `accepted` или `rejected`. | Human Gate: нет открытых блокирующих Decisions. |
| `analyzing` | `analyzed` | Завершён анализ всех слайсов, вычислены дельты, проведено глобальное согласование. `deltafuse next` даёт один Analyze pass за раз; комплект тот же. | На диске есть `routing.yaml`, срезы на каждую routing primary capability и `coverage.yaml`; все claims покрыты; дельты типизированы. |
| `analyzed` | `specification-proposed` | Требуется изменение спецификации (`requirement_delta: modify/add`). `deltafuse next` даёт один Specify-срез (`spec_refs` только), затем `close`. | Сформирован проект правок в файлах `spec_refs` срезов и `spec-delta.md`, и все машинные проверки гейта `specified` проходят, кроме двух, которые человек закрывает при принятии: его receipt и возможность из routing, ещё находящаяся в статусе `draft`; иначе `deltafuse state` отказывает и возвращает ошибки воркеру. |
| `analyzed` | `decomposed` | Багфикс: изменение спецификации не требуется (`requirement_delta: none`); `deltafuse next` сразу даёт Decompose. | Гейт `decomposed` доказывает точные ссылки задач на существующие требования `REQ-*`; с другим intent (тем, что записан в receipt гейта intake, а не тем, что сейчас в change.yaml), с `spec-delta.md`, который что-то добавляет, меняет или удаляет, или с деревом `docs/spec/**`, отличающимся от записанного на Intake, он отказывает: такой Change идёт через Human Gate спецификации. `intent` задаётся до закрытия Intake (`deltafuse state <change-dir> --change --intent bugfix`) и после не меняется. |
| `specification-proposed` | `specified` | Правки в спецификации согласованы и смерджены. | Human Gate: утверждённые правки в `docs/spec/**`. Receipt принятия хранит digest текста каждого раздела, на который ссылаются spec-delta и срезы; пока один из них отличается от диска, все последующие гейты отказывают. |
| `specified` … `verifying` | `analyzed` | Человек отклоняет уже принятую спецификацию: `deltafuse decide <change-dir> --spec --status rejected`. | Verification, Green и regression уходят в `reopened/verify.<n>/`, срезы возвращаются в `draft`, реализованные задачи — в `declared`; после нового принятия ядро проходит гейты, которые задачи уже проходили. |
| `implemented` / `verifying` | `declared` | Человек переоткрывает задачу, заблокированную после гейта `implemented`: `deltafuse decide <change-dir> --task <id> --status reopened`. | Задача объявляется и реализуется заново, гейт `implemented` проходится снова. |
| `specified` | `decomposed` | Завершён `/decompose`. Созданы атомарные задачи `TASK-NNN`. | Все требования слайсов покрыты задачами с явным Test Oracle. |
| `decomposed` | `declared` | `deltafuse advance <change-dir> --gate declaring`, когда каждая задача `declared` (промежуточный `declaring` перешагивается, см. ниже). | Каждая задача, кроме `cancelled` и `superseded`, `declared` со своим Red evidence. |
| `declaring` | `declared` | Тестовый таргет упал строго по ожидаемой поведенческой причине. | Для каждой задачи записан `evidence/red/<task-id>.yaml`, код продукта не изменён. |
| `declared` | `implementing` | Запущен `/implement`. Начато изменение продуктового кода. | Скоуп файлов ограничен контрактом задачи. |
| `implementing` | `implemented` | Тестовый таргет стал Green, scoped regressions прошли успешно. | Для каждой задачи записаны `evidence/green/<task-id>.yaml` и `evidence/regression/<task-id>.yaml`. На `route: code` Green отвечает на Red, который действительно падал: Green поверх `already-green` Red не доказывает дельту и гейт не закрывает. Задачу с `already-green` Red и `requirement_delta: none` уже выполнила работа вокруг неё: Worker закрывает её как `superseded` (`deltafuse state --task <id> --status superseded`, ядро разрешает только в этом случае; тест остаётся регрессионным). Задача, обещавшая дельту требований, останавливается до решения человека. |
| `implemented` | `verifying` | Все задачи пакета Change переведены в состояние `implemented`. | Нет незавершённых или зависших задач. |
| `verifying` | `converged` | Запущен `/verify`. Доказана сквозная трассируемость и сходимость всех слоёв. | Все объявленные дельты применены, тесты зелёные, расхождений нет; `spec-delta.md` принят человеком (receipt `decide --spec` на его текущих байтах; без него сходится только багфикс с неизменной спецификацией). |
| `implemented` / `verifying` | `analyzing` | Verify записал `spec-gap` или `tasks-missing`; человек переоткрывает его: `deltafuse decide <change-dir> --gap <gap> --status reopened`. | **Escalation Gate**: возврат на анализ только решением человека (квитанция `gap-reopen`), без несанкционированных правок. |
| `verifying` | `not-reproduced` | Закрытие Change как невоспроизведённого дефекта или подтверждённого no-op. | В `verification.md` зафиксирован исход `not-reproduced`. |
| `analyzing` / `declaring` | `not-reproduced` | Дефект не воспроизводится на кодовой базе; Red-тест не выявил ожидаемого сбоя. | Зафиксирован диагностический отчёт или evidence со статусом `result: not-reproduced`. |
| любой статус до `converged` | `rejected` | Запрос нереализуем, отвергнут или Change не будет доведён. | Решение человека с обоснованием (`--note`). |
| `normalized` / `analyzing` / `analyzed` | `duplicate` | Запрос дублирует уже существующий активный или архивный Change. | Решение человека; заметка называет оригинальный `CHG-*`. |
| любой статус до `converged` | `superseded` | Change заменён более широким или реструктурированным запросом. | Решение человека; заметка называет замещающий `CHG-*`. |
| `declared` / `implementing` | `not-reproduced` | Все задачи закрыты (`superseded` на already-green Red или `cancelled`): реализовывать нечего. `deltafuse next` останавливается и называет команду закрытия. | Red с `result: not-reproduced` или `already-green`. |
| `converged` | `archived` | Пакет Change целиком перемещён в `docs/archive/changes/<date>-<change-id>/`. | Change удалён из активных списков, история неизменна. |

Терминальные `rejected`, `duplicate`, `superseded` и `not-reproduced` пишет только `deltafuse decide <change-dir> --close --status <status> --note "<почему>"` (с паролем Human Gate, если он задан) из статуса, который допускает таблица (`rejected` и `superseded` — из любого статуса до `converged`); для `not-reproduced` из Declare нужен Red с `result: not-reproduced` или `already-green`, из Verify — `- Outcome: not-reproduced` в `verification.md`. Команда пишет receipt статуса в `transitions.jsonl` и receipt Human Gate на `change.yaml`; терминальный статус, записанный руками, останавливает `deltafuse next`, не архивируется и оставляет Change активным для защиты `init --force`.

Статусы `declaring`, `implementing` и `verifying` в Change не пишет ни одна команда: работа воркера в этих фазах записывается в его задачи. `deltafuse advance` закрывает следующий гейт из статуса покоя, перешагивая промежуточный, — `decomposed` → `declared`, `declared` → `implemented`, `implemented` → `converged`, — и receipt записывает этот шаг. Промежуточный статус на один законный шаг после последнего receipt Change держать по-прежнему может. Любой другой статус, не подтверждённый журналом, — `converged`, `archived`, `blocked-on-decision` без предложенного Decision, отмотанный руками статус — останавливает `deltafuse next` и все команды ядра; прерванный `advance` завершает только `advance` того же гейта. Действует последний вердикт человека по артефакту: принятие, за которым последовало переоткрытие или отклонение, не засчитывается, даже если байты файла вернуть.

Гейты `declaring` и `implemented` проверяют каждую задачу, кроме `cancelled` и `superseded`: каждая должна быть на статусе гейта со своим evidence. У закрытой задачи гейты и очередь спрашивают, чем она закрыта: `cancelled` — вердиктом человека `decide --task`, `superseded` — receipt команды `deltafuse state` и already-green Red у задачи с `requirement_delta: none`; статус, выставленный руками, останавливает гейты. Decision, привязанный к Change (`proposed` или принятый без `decide`), останавливает каждый гейт, а не только Analyze и Specify. Гейты, `state`, `evidence` и `next` отказывают, если config не совпадает с lock или работающее ядро — не то, что закреплено в lock (`decide` не отказывает: Change можно закрыть перед обновлением). Green и regression evidence штампуются деревом `docs/spec/**` и корней кода продукта (`workflow.code_roots`, иначе `src/**` и `tests/**`), включая тесты; следующая задача, меняющая его, делает evidence предыдущей устаревшим, и `deltafuse next` направляет воркера перезапустить evidence этой задачи на текущем дереве, прежде чем гейт закроется.

---

## Slice State Machine

Срез (`slices/SLICE-NN.md`) — независимо проверяемая часть Change. Ядро ведёт для него два
статуса и один переход:

```text
draft -> specified        deltafuse state <change-dir> --slice <id> --status specified
specified -> draft        только решением человека: decide --gap / decide --spec --status rejected
```

- `draft`: срез записан в Analyze; Specify берёт срезы в `draft` по одному;
- `specified`: Specify записал часть спецификации этого среза; `deltafuse next` его больше не называет. Обратно в `draft` все срезы Change возвращает только `decide` человека: переоткрытый gap из Verify или отклонение уже принятой спецификации.

Схема среза по-прежнему допускает `analyzing`, `blocked`, `analyzed`, `decomposed` и `verified`,
и Specify читает `decomposed` и `verified` как уже специфицированные, но ни одна команда ядра их
не пишет: что происходит со срезом после Specify, записано в его задачах и в Change.

---

## Task State Machine

Состояния отдельных атомарных задач (`tasks/TASK-NNN-<slug>.md`):

```text
[pending] ---> [declaring] ---> [declared] ---> [implementing] ---> [implemented] ---> [verified]
  |  |  ^           |               |                 |                   |
  |  |  |           +---------------+--------+--------+-------------------+
  |  |  |                                    v
  |  |  +-- человек: reopened ---------- [blocked] --- человек ---> [cancelled]
  |  |
  |  +--> [declared]  (Red записан сразу, минуя declaring)
  |
  +-----> [cancelled] (человек) / [superseded]
```

- `pending`: задача создана, ожидает выполнения зависимостей; дальше — `declaring`, `declared`, `cancelled` (только человек) или `superseded`;
- `declaring`: пишется минимальный тест, доказывающий Red;
- `declared`: зафиксирован воспроизводимый Red evidence;
- `implementing`: пишется минимальный продуктовый код;
- `implemented`: тест и регрессии прошли успешно (Green evidence);
- `verified`: сходимость задачи подтверждена в ходе общей верификации Change;
- `blocked`: заявленный оракул оказался неверным; запуск останавливается до решения человека. Достижим из `pending` (если Red уже записан), `declaring`, `declared`, `implementing` и `implemented`. Воркер ставит его (`deltafuse state <change-dir> --task <id> --status blocked`) только после того, как ядро записало Green против оракула, замороженного Red, и тесты оракула не изменены;
- `cancelled`: задача отменена — только решением человека, не воркера: `deltafuse decide <change-dir> --task <id> --status cancelled` (пароль Human Gate, если задан; квитанция вида `task` в журнале). `deltafuse state` такой переход отказывает;
- из `blocked` выходит только человек: отменой (выше) или переоткрытием `deltafuse decide <change-dir> --task <id> --status reopened [--note "<почему>"]` — доказательства задачи переносятся в `reopened/<task>.<n>/`, её продуктовые файлы возвращаются к копиям, снятым гейтом `declaring`, в журнал пишется квитанция `task`/`reopened`, задача возвращается в `pending`, и только её можно объявить заново, когда Change уже `declared` или `implementing`;
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
schema_version: 3
framework:
  version: <framework-version>
  content_hash: sha256:...
```

`routing.yaml` и `coverage.yaml` не требуют `schema_version`; неизвестные ключи верхнего уровня там игнорируются.

Активный Change обязан завершаться в соответствии с зафиксированной версией фреймворка. Обновление внешнего DeltaFuse фреймворка не меняет семантику активных Changes автоматически; миграция активных процессов требует явной процедуры.
