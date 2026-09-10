# A00-05 — Bash smoke и layout

**Verdict: `pass` для BASE-005 (с выявлением дефекта [F-001](../../findings/F-001.md)).** На ревизии `60ea40438b0142797848356c660ab88286565e7d` (рабочий HEAD `d9ca00f40d42171120f3e6c0cbe27ef48ae5bb9a`) в среде WSL2 Ubuntu 24.04 (Linux 6.6.87.2, GNU bash 5.2.21) проверены скрипты дистрибьюции и валидации layout:
1. При запуске из чистого tar-архива ревизии с сохранением канонических окончаний строк LF (`core.autocrlf=false`) сквозной smoke-тест `tests/smoke-test.sh` и все 4 шага валидации завершились с exit code 0.
2. При прямом запуске из рабочего дерева, чекаученного под Windows с `core.autocrlf=true`, воспроизведён дефект окончания строк CRLF: bash падает с ошибкой `set: pipefail\r: invalid option name` (exit code 2), что оформлено как дефект [F-001](../../findings/F-001.md).

| Показатель | Наблюдение | Evidence |
|---|---|---|
| Окружение | Ubuntu 24.04.3 LTS на WSL2 Linux 6.6.87.2 x86_64, GNU bash 5.2.21, awk, sed, sha256sum | [bash-info-1.txt](bash-info-1.txt) |
| Прямой запуск на Windows checkout | Сбой `set: pipefail\r: invalid option name`, exit code 2 (причина: CRLF при отсутствии `.gitattributes`) | [smoke-crlf-fail-1.txt](smoke-crlf-fail-1.txt), [F-001](../../findings/F-001.md) |
| Сквозной smoke-тест (LF) | `tests/smoke-test.sh`: 4/4 этапа пройдены успешно, exit code 0 (1.29 с) | [smoke-1.txt](smoke-1.txt) |
| Чистая установка (LF) | `scripts/init.sh <isolated-product>`: exit code 0 (0.77 с) | [init-fresh-1.txt](init-fresh-1.txt) |
| Валидация layout после init | `tests/validate-layout.sh <isolated-product>`: exit code 0 (0.17 с) | [validate-fresh-1.txt](validate-fresh-1.txt) |
| Структура установленного продукта | 56 файлов (полное совпадение списка путей с инвентарем A00-04) | [layout-inventory.json](layout-inventory.json) |
| Хеш содержимого фреймворка (LF) | `sha256:f1c2298ce5dbabacdefa0e700ad84770a4d80ddc031e2dcb12d87fe2c3a55f56`, версия `2.0.0`, source `deltafuse://v2.0.0` | [layout-inventory.json](layout-inventory.json) |
| Повторная установка (--force) | `scripts/init.sh --force <isolated-product>`: exit code 0, сохранение 13 файлов (0.77 с) | [init-force-1.txt](init-force-1.txt) |
| Повторная валидация layout | `tests/validate-layout.sh <isolated-product>`: exit code 0 (0.16 с) | [validate-force-1.txt](validate-force-1.txt) |
| Целостность исходников | Рабочее дерево Git проверено; изменения за пределами `backlog/**` отсутствуют | [source-integrity.json](source-integrity.json) |

Все проверки проводились в изолированных временных каталогах `/tmp/a00-05-*` внутри WSL. Исходный код рабочего дерева фреймворка не модифицировался. Полный журнал вызовов зафиксирован в [state.json](state.json), автоматизация — в [run.ps1](run.ps1).

### Ключевые наблюдения
- **[F-001](../../findings/F-001.md):** В репозитории отсутствует `.gitattributes`. При чекауте на Windows скрипты `tests/smoke-test.sh` и `tests/validate-layout.sh` получают CRLF, что ломает исполнение в Linux/WSL Bash.
- **Расхождение хеша фреймворка из-за CRLF:** Хеш содержимого в lock-файле вычисляется по сырым байтам файлов. Поэтому на Windows (CRLF) получается хеш `sha256:64b3...`, а на Linux (LF) — `sha256:f1c2...`. Это нарушает кросс-платформенную воспроизводимость lock-файла продукта.

## Handoff

- **BASE-005 выполнен:** Bash smoke (`tests/smoke-test.sh`) и валидация структуры продукта (`tests/validate-layout.sh`) в Linux-окружении из канонического LF-дерева воспроизводимо проходят с exit code 0.
- **Пакет A00 полностью завершён:** зафиксированы ревизия (A00-01), карта компонентов (A00-02), результаты pytest (A00-03), PowerShell smoke/layout (A00-04) и Bash smoke/layout (A00-05).
- **Оформлена первая находка:** [F-001](../../findings/F-001.md) (дефект CRLF / отсутствие `.gitattributes`).
- **Следующая задача:** [A01-01 — Опредерить критерии качества спецификации](../../packets/A01-01.md).
