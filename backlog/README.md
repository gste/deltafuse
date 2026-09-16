# DeltaFuse backlog

Здесь находится только живая очередь работ. Завершённые карточки и старые
аудиторские материалы сохраняются в истории Git, но не остаются в рабочем
дереве.

- Текущая очередь: [product/index.md](product/index.md)
- Активная программа: [product/deltafuse-3.md](product/deltafuse-3.md)
- Текущий план исправлений:
  [product/v3/qualification-fix-plan-wave-3.md](product/v3/qualification-fix-plan-wave-3.md)
- Предыдущий план исправлений:
  [product/v3/qualification-fix-plan-wave-2.md](product/v3/qualification-fix-plan-wave-2.md)
  и
  [product/v3/qualification-fix-plan.md](product/v3/qualification-fix-plan.md)
- Исходный план завершения:
  [product/v3/completion-plan.md](product/v3/completion-plan.md)
- Текущая карточка: [product/DF3-009.md](product/DF3-009.md)


## Прочее

- [ ] В версии 2.5.0 при установке поставляется `deltafuse-leash.yml` с некорректными наименованиями папок delta-fuse (через дефис)
- [ ] В файле lock.yaml некорректный хэш версии 2.5.0
- [ ] При установке deltafuse нужно также делать append лишних артефактов в `.gitignore` хост-проекта. также нужно сделать ревизию таких артефактов. по возможности стоит разделить по разным директориям.
- [ ] AGENTS.MD может clash-иться с таким же файлом если хост-проект подразумевает свой AGENTS.md. тогда для deltafuse его надо куда-то перенести?
- [ ] В разных проектах Warning:
    Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/checkout@v4, actions/setup-python@v5...
