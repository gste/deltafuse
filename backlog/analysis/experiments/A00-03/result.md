# A00-03 — исходный прогон pytest

**Verdict: `pass` для BASE-003.** На ревизии `60ea40438b0142797848356c660ab88286565e7d` выполнен `python -m pytest -v`: 91 тест собран, 91 прошёл, exit code 0.

| Показатель | Наблюдение | Evidence |
|---|---|---|
| Окружение | Windows 11 AMD64, CPython 3.14.3, отдельная venv | [python-info-1.txt](python-info-1.txt) |
| Зависимости | pytest 9.1.1, jsonschema 4.26.0, PyYAML 6.0.3 | [pip-freeze-1.txt](pip-freeze-1.txt) |
| Проверка зависимостей | `pip check`: exit 0 | [pip-check-1.txt](pip-check-1.txt) |
| Pytest | 91/91 passed, exit 0; 10.96 с по отчёту | [pytest-1.txt](pytest-1.txt) |
| Целостность исходников | 206 файлов архива проверены после тестов; changed/missing: 0/0 | [source-integrity.json](source-integrity.json) |

Исходники экспортированы через `git archive` в отдельный временный каталог; зависимости установлены только по `pyproject.toml`. User site и автозагрузка внешних pytest plugins отключены. Полный вызов и exit codes сохранены в [state.json](state.json), процедура — [run.ps1](run.ps1).

Проверка ограничена Windows/Python 3.14.3. Другие Python и платформы, smoke/layout, CI eval и локальная LLM `ornith-1.5-35b-a3b` через LM Studio не проверялись. Успешный pytest не доказывает полноту требований или качество продуктовых тестов.

Ошибки sandbox при первичном обнаружении uv и запуске Python устранены разрешённым запуском вне sandbox; это ошибки подготовки, не ошибки pytest. Старый `EX-001/pytest.log` не использовался как evidence.

## Handoff

- BASE-003 выполнен: новый воспроизводимый локальный прогон — 91/91, exit 0.
- Неизвестны результаты shell smoke/layout и CI; их выполняют A00-04/A00-05.
- Следующая задача: A00-04 — PowerShell smoke и layout.
