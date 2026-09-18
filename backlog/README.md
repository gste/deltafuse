# DeltaFuse backlog

Здесь находится только живая очередь работ. Завершённые задачи сохраняются в истории Git.

## Прочее

- [x] В версии 2.5.0 при установке поставляется `deltafuse-leash.yml` с некорректными наименованиями папок deltafuse (без дефиса)
- [x] В файле lock.yaml некорректный хэш версии 2.5.0
- [x] Проверка генерации хэшей lock.yaml: проверена консистентность генерации хэшей между src/deltafuse/core/hasher.py, scripts/init.ps1, scripts/init.sh и src/deltafuse/core/installer.py. Хэши совпадают бит-в-бит (sha256:...).
- [x] При установке deltafuse нужно также делать append лишних артефактов в `.gitignore` хост-проекта. также нужно сделать ревизию таких артефактов. по возможности стоит разделить по разным директориям.
- [x] AGENTS.MD не перезаписывается при установке в хост-проект с собственным AGENTS.md (инstaller сохраняет существующий файл).
- [ ] В разных проектах Warning:
    Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on Node.js 24: actions/checkout@v4, actions/setup-python@v5...
