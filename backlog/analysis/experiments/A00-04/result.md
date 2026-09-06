# A00-04 — PowerShell smoke и layout

**Verdict: `pass` для BASE-004.** На ревизии `60ea40438b0142797848356c660ab88286565e7d` (рабочий HEAD `03c89109a9fc0305f38733138a60c194512397c4`) выполнен PowerShell smoke-тест и поэтапная валидация структуры продукта: все шаги завершились с exit code 0, layout валиден как при чистой установке, так и после повторной установки с флагом `-Force`.

| Показатель | Наблюдение | Evidence |
|---|---|---|
| Окружение | Windows 11 build 10.0.26200 AMD64, PowerShell 7.6.5 (Core), ConsoleHost 7.6.5 | [powershell-info-1.txt](powershell-info-1.txt) |
| Сквозной smoke-тест | `tests/smoke-test.ps1`: 4/4 этапа пройдены, exit code 0 (5.56 с) | [smoke-1.txt](smoke-1.txt) |
| Чистая установка | `scripts/init.ps1 -TargetDir <isolated-product>`: exit code 0 (5.14 с) | [init-fresh-1.txt](init-fresh-1.txt) |
| Валидация layout после init | `tests/validate-layout.ps1 -ProductDir <isolated-product>`: exit code 0 (4.72 с) | [validate-fresh-1.txt](validate-fresh-1.txt) |
| Структура установленного продукта | 56 файлов (AGENTS.md, CHANGELOG.md, config, lock, 21 skill-файл и маркер в 3 адаптерах, 10 docs-шаблонов) | [layout-inventory.json](layout-inventory.json) |
| Хеш содержимого фреймворка | `sha256:64b3cdb786e23c4233cdc92a84ebbae4966fb72abe49c08b5675b7a76b85119f`, версия `2.0.0`, source `deltafuse://v2.0.0` | [layout-inventory.json](layout-inventory.json) |
| Повторная установка (-Force) | `scripts/init.ps1 -TargetDir <isolated-product> -Force`: exit code 0, сохранение 13 существующих файлов (5.30 с) | [init-force-1.txt](init-force-1.txt) |
| Повторная валидация layout | `tests/validate-layout.ps1 -ProductDir <isolated-product>`: exit code 0 (0.43 с) | [validate-force-1.txt](validate-force-1.txt) |
| Целостность исходников | Рабочее дерево Git проверено; изменения за пределами `backlog/**` и временных каталогов отсутствуют | [source-integrity.json](source-integrity.json) |

Установка и проверки выполнялись исключительно в изолированных временных каталогах; рабочий репозиторий и продукты пользователя не затрагивались. Полный перечень команд, таймингов и контрольных сумм зафиксирован в [state.json](state.json), процедура автоматизации — в [run.ps1](run.ps1).

Проверка ограничена платформой Windows и PowerShell 7.6.5. Bash-эквиваленты (`tests/smoke-test.sh`, `scripts/init.sh`, `tests/validate-layout.sh`) и CI не проверялись в этой карточке и вынесены в A00-05. Локальная модель `ornith-1.5-35b-a3b` через LM Studio не запускалась. Успешный smoke-тест подтверждает целостность скриптов дистрибьюции и валидатора структуры, но не доказывает семантическую полноту требований или качество продуктового кода.

## Handoff

- **BASE-004 выполнен:** PowerShell smoke (`tests/smoke-test.ps1`) и валидация структуры продукта (`tests/validate-layout.ps1`) воспроизводимо проходят с exit code 0.
- **Подтверждено:** корректная генерация 56 файлов продукта, генерация адаптеров `.agents/skills`, `.cursor/skills`, `.gemini/skills` с маркерами `.deltafuse-generated.yaml` и баннерами `DO NOT EDIT`, расчёт хеша содержимого фреймворка и сохранение файлов при `-Force`.
- **Неизвестно:** воспроизводимость на Bash/Linux/macOS (`tests/smoke-test.sh`, `scripts/init.sh`, `tests/validate-layout.sh`).
- **Следующая задача:** [A00-05 — Проверить Bash smoke и layout](../../packets/A00-05.md).
