# Аудит размера кодовой базы DeltaFuse (2026-10-21)

**Состояние: аудит, к решению владельца.** Ветка `chore/codebase-audit` от `origin/master` (`8290721`, 3.3.8).
Ничего не менялось: пять независимых проходов только на чтение (ядро по группам модулей, CLI и Artifact
Writer, навыки) и `vulture`. Покрытие тестами — отдельным разделом, когда прогон закончится.

## 1. Итог

| | сейчас | после безопасных правок | после решений владельца |
| --- | --- | --- | --- |
| `src` (Python, без assets) | 19.4K строк | ≈ −1.5K (−8%) | ≈ −2.4K (−12%) |
| навыки (`process/skills`) | 41.3 KB | ≈ 36 KB (−13%) | — |

Ни одна правка не ослабляет проверку: каждый отказ ядра остаётся с тем же условием, сообщение может
стать короче, но по-прежнему называет, что делать. Сокращение в 2–3 раза невозможно без удаления
возможностей: рост шёл не повторяющейся логикой, а одним и тем же кодом чтения файлов и отказов,
скопированным в каждую заплатку (69 ссылок на прогоны в комментариях `src`).

Оценки по модулям (агенты, перекрытия между ними учтены грубо):

| область | строк в области | безопасно | по решению владельца |
| --- | --- | --- | --- |
| `fsm.py`, `evidence.py`, `test_reports.py`, `oracle.py` | 2 613 + | ≈ 200 | — |
| `transitions.py`, `decide.py`, `gate_receipts.py`, `task_snapshot.py`, `spec_baseline.py`, `artifact_transactions.py` | 2 611 | ≈ 235 | 70 (R1) |
| `queue.py`, `leash.py`, `context.py`, `analyze.py`, `integrity.py`, `specify.py` | 4 296 | ≈ 430–480 | — |
| `cli.py`, Artifact Writer, `installer.py`, `schemas.py` | ≈ 5 000 | ≈ 445 + 300 средний риск | ≈ 880 (A1, A5, A6, validate) |

## 2. Найденные ошибки (важнее объёма)

Подтверждены мной по коду:

1. **Проход `gap` в навыке analyze может не закрыть шлюз.** Шаг 2 велит закрыть `analyzed` «as step 3
   says», а шаг 3 закрывает только при `analyze_pass: coverage`. Причина в `next` при этом говорит «Then
   check-gate analyzed and advance» (`analyze.py:293`), а `check-gate` навыки запрещают; то же в блоке «Close
   the gate» (`queue.py:1119-1121`). Правка: «If `analyze_pass` is `coverage` or `gap`…» и убрать `check-gate`
   из причин. Это путь назад после spec-gap из 3.3.8.
2. **При записи теряются два отказа о `changed_paths`.** `_contract_errors_now` (`evidence.py:201-204`)
   оставляет только сообщения с `"{dest.name}:"`, а сообщения о `forbidden_paths` (`fsm.py:1167-1170`) и о
   продуктовом коде на маршруте docs/ops (`fsm.py:1160-1164`) двоеточия после имени файла не имеют. Запись
   говорит «authentic», шлюз отказывает шагом позже — ровно то, что исправляла правка shopkit.
3. **`pytest.cmd` роняет изолированный прогон Green.** `oracle.py:373` снимает с имени раннера только
   `.exe`, а `runner_family` — ещё `.cmd`/`.bat`; для `pytest.cmd` `argv.index("pytest")` даёт `ValueError`.
4. **Совет после already-green читает не тот файл.** `already_green_advice` (`transitions.py:709`) читает
   `tasks/{id}.md` напрямую; для `TASK-NNN-<slug>.md` теряет `requirement_delta` и отправляет к человеку
   задачу, которую можно закрыть `superseded`. Отказы не затронуты, только совет.

Найдены агентами, мной не перепроверены:

5. **`check-gate --gate <опечатка>` проходит**: у `_check_gate` нет ветки для неизвестного шлюза, а
   `gate_order_errors` для него пуст.
6. **`recover_pending_transactions` не вызывается ядром**, хотя `docs/using.md:199` говорит, что ядро
   восстанавливает транзакции. Либо подключить, либо удалить вместе с тестами и исправить документацию.
7. **Переоткрытие задачи в leash не привязано к Change**: `reopen_archive_path` / `reopened_red_path`
   проверяют `has_click` по id задачи, так что переоткрытие TASK-001 в одном Change покрывает TASK-001 в
   другом. `gate_receipts.task_reopened` уже умеет по Change.
8. **`task_evidence_summary` (сводка в `coverage.yaml`) проверяет не всё, что шлюз `implemented`**: нет
   already-green, «нет Red» и условия `route == code`, хотя docstring обещает те же проверки.
9. **`leash._change_dirs` жёстко берёт `docs/changes`**, а `queue.changes_dir` читает `paths.changes`.
10. Устаревшие строки навыков: declare шаг 3 упоминает `check-gate --gate converged`; последняя строка
    verify («Specify still does not write deploy YAML») к Verify не относится; analyze строка 108 о
    неизвестных ключах устарела после Artifact Writer.
11. Копии навыков в бенче (`qualify/skill_variants/_master`) отстали от фреймворка (нет прохода gap,
    исключения в specify и др.).

## 3. Безопасные правки (механика, ≈ 1.5K строк)

Общие помощники вместо копий — основной выигрыш:

- **Чтение записей и frontmatter.** Одно `_load_record` / `iter_frontmatter` вместо ≈ 20 копий
  try/except в `fsm.py`, `evidence.py`, `transitions.py`, `queue.py`, `leash.py`, `analyze.py`,
  `integrity.py`. Проверки `isinstance(meta, dict)` после `parse_frontmatter` мертвы: он всегда отдаёт
  dict или бросает (≈ 70 строк).
- **JSONL, атомарная запись, config.yaml.** `read_jsonl` (≈ 10 копий в `transitions`, `gate_receipts`,
  `leash`), `atomic_write` (≈ 6 копий), `config_section` (7 чтений `.deltafuse/config.yaml`) (≈ 60).
- **`queue.py`.** Конструктор `_blocked(...)` для 9 почти одинаковых `WorkItem(kind="blocked")`,
  замыкание для 12 `_item_for_step`, один `PassCursor` вместо `AnalyzeCursor`/`SpecifyCursor`, общие
  блоки форматирования analyze/specify (≈ 150).
- **Проверки «при записи» и «на шлюзе».** Одна функция на правило вместо двух-трёх текстов: прогон без
  тестов (3 места), устаревший `base_revision` (2), Red против Green (3 места с разными списками — заодно
  чинит п. 8 раздела 2), таблица фаза→шлюз (2 копии) (≈ 70).
- **`_is_authentic` избыточен**: каждый случай False уже кладёт ошибку в `errors`, итог и так `authentic
  and not errors`; остаётся расширить проверку кода выхода на verification (≈ 35).
- **`decide.py`.** Общие помощники нумерации и архивации для `reopen_task` / `reopen_gap`, проверки
  каталога Change (4 копии сообщения) и заметки (≈ 55).
- **`artifact_transactions.py`.** Чтение журнала (5 копий), 6 параметров, которые никто не передаёт, и
  недостижимая очистка `staged_path` (≈ 65).
- **CLI.** `_fail(...)` для 12 одинаковых троек «журнал + печать + код выхода», `_print_errors`, общий
  вид для validate/validate-layout/validate-config, сжатие 318 строк `add_argument` (≈ 140).
- **Мёртвое** (проверено grep по `src/` и `tests/`): `GateValidationError`, `IntegrityViolation`,
  `PRODUCT_WRITE_GLOBS`, `_PRODUCT_CODE_GLOBS`, `ANALYZE_PASSES`, `EvidenceOutcome.command_exit_code`,
  `get_envelope_schema_hash`, `SchemaValidationError`/`validate_or_raise`, неиспользуемые импорты в
  `cli.py`/`artifacts.py`/`decide.py`/`leash.py`, повторные локальные импорты, `RECEIPT_CHAIN` (=
  `GATE_TARGETS`), недостижимая ветка в замене цепочки (`transitions.py:358-362`) (≈ 100).
- Функции только для тестов (`validate_operation_input`, `cleanup_orphaned_staging`,
  `revalidate_authorization_context`, `last_receipt`, `estimate_tokens`, `get_installed_lock_hash`) —
  удалить или перенести в фикстуры (≈ 150).

## 4. Средний риск (≈ 300 строк, нужны тесты-фиксаторы)

- `ArtifactRegistry.validate_references` — пять раз строит одни и те же пути-кандидаты (≈ 150); порядок
  кандидатов решает, какой файл найден, нужны тесты на равенство.
- `ArtifactService.create`/`update` — повтор идемпотентности (3), публикации и подтверждения (2) (≈ 90).
- Два валидатора схем над одними файлами (`SchemaRegistry` и `ArtifactRegistry.validate_storage_schema`,
  последний заново строит валидатор на каждый вызов и не нормализует даты) (≈ 30).
- **Перед правкой `queue.py`**: у многих причин и подсказок `next` нет ни одного теста («Every task is
  declared», «predates later», «Bugfix may skip», все тексты halt). Сначала один «золотой» тест,
  фиксирующий эти строки, иначе упрощение незаметно поменяет то, что читает модель.

## 5. Решения владельца (≈ 900 строк)

| | что | строк | кто зависит |
| --- | --- | --- | --- |
| A1 | убрать старые `artifact describe/create/update/validate/update-index` (навыки и бенч используют только `artifact write`) | ≈ 720 | `docs/using.md`, ≈ 5 файлов тестов |
| A1b | если оставить — свести create/update к общим помощникам; **сейчас коды выхода расходятся** (create: 3, update: 5 на одни и те же ошибки) | ≈ 200 | — |
| R1 | `recover_pending_transactions`: подключить или удалить (см. раздел 2, п. 6) | 70 | 1 интеграционный тест |
| A5 | убрать `lint-context` — подмножество `validate_change_package` | ≈ 70 | документация, 3 теста |
| A6 | убрать CLI-обёртку `deltafuse bench init/journal` — бенч зовёт Python API | ≈ 65 | только документация |
| — | `validate`, `validate-layout` — ни навыки, ни бенч | ≈ 25 | документация, 1 тест |
| — | бенч-функции во фреймворке (`assert_scorecard_outside_sandbox`, `summarize_journal`) перенести в `deltafuse-bench` | ≈ 30 | бенч |

## 6. Навыки (41.3 → ≈ 36 KB)

Удаляются только предложения, которые повторяют другое предложение того же навыка или отказ ядра,
называющий исправление в нужный момент. Правила остаются.

| навык | сейчас | после | что уходит |
| --- | --- | --- | --- |
| analyze | 8.1 KB | ≈ 7.3 | устаревшая строка 108, повтор строки 102, пояснения «почему» |
| verify | 5.4 | ≈ 4.3 | повтор контекста в шагах 4–5 и 9, чужая последняя строка |
| declare | 6.2 | ≈ 5.2 | устаревшее про `check-gate`, длинный абзац о переоткрытой задаче (≈ 600 → 200 B) |
| implement | 5.3 | ≈ 4.5 | повторы отказов ядра о замороженном оракуле и `blocked` |
| specify | 5.2 | ≈ 4.8 | повторы шага 1 и закрывающего прохода |
| decompose | 4.8 | ≈ 4.6 | описание следующего шага, повтор отказа leash |
| intake | 3.3 | ≈ 3.2 | три повтора |
| run | 3.0 | ≈ 2.5 | раздел Halt повторяет шаги 6–7, «Never git push» трижды |

Ограничения: тесты закрепляют часть формулировок (маркеры Worker'а, ровно один `advance` на навык,
счётчики `deltafuse state`, ряд фраз declare/implement/specify/analyze/intake/run), они должны
остаться. Шаги 4–5, одинаковые в семи навыках (≈ 420 B), можно заменить ссылкой на `/run`, но это
ломает запуск одного шага без `/run` — только после прогона в бенче.

## 7. Чего не делать

- **Таблицы-реестры вместо `check_gate`, проверок `set_artifact_status` и цепочки `_scan_change`.**
  Строк не убавят (+10 и ≈ 0 по оценкам), а порядок проверок решает, какой отказ увидит Worker, и
  таблица его спрячет. Единственная польза реестра — отказ на неизвестный шлюз — делается двумя строками.
- **Слияние исключений leash в glob.** `fnmatch` на Windows не различает регистр, и `readme.md` /
  `agents.md` стали бы исключениями — это ослабление.
- **Правка `skill_variants` в бенче вручную** — только перекопировать из обновлённых навыков и
  пересобрать `build.py`, иначе второй дрейф.

## 8. Порядок работ

1. Ошибки раздела 2, п. 1–4 (малые правки, каждая со своим тестом) — до любой чистки.
2. «Золотой» тест на тексты `next`/halt.
3. Безопасные правки раздела 3 модуль за модулем, полный набор тестов после каждого.
4. Решения раздела 5 — по ответу владельца.
5. Навыки — одним коммитом, затем `sync_assets.py` и перекопирование `skill_variants`.
6. Квалификация M01–M04 на итоговом коммите: она проверит и 3.3.8, и упрощение сразу.

Плюс два новых запроса Fuse-Back к 3.3.8, ещё не разобранных: `q6-fuse-back/GAP-REOPEN-COMMIT.md`
(шлюз `analyzed` после `decide --gap` отказывает до коммита) и `q6-fuse-back/SNAPSHOT-LONG-PATHS.md`
(снимок `declaring` удлиняет пути на Windows).
