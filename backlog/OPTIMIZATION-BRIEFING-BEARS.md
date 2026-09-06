# Optimization briefing: медведи (W00–W07)

Канонический запуск в репозитории DeltaFuse: [analysis/experiments/local-runtime/README.md](analysis/experiments/local-runtime/README.md).

**Для кого.** Нагрузка уровня анализа: длинный префилл, многофайловый YAML, «сначала routing», минимальный файловый агент.  
**Статус.** Очередь закрыта. CLI сервера **не** меняли относительно кроличьего frozen.

Сводка **кроликов** (thinking-off, cpu-moe, ctx, квант): [OPTIMIZATION-BRIEFING.md](OPTIMIZATION-BRIEFING.md).  
Машиночитаемый профиль: [experiments/W07-01/workload-profile.yaml](experiments/W07-01/workload-profile.yaml). Доска: [index.md](index.md).

Дата: 2026-09-06. Репозиторий `llm-optimization`. Синтетический продукт — склад `inventory.stock` / `CHG-240`, не калибровка чужого репо.

Сырьё: `experiments/Wxx-01/result.md`, `experiments/bench-runs/*-W0*`, `experiments/agent-runs/`.

---

## 1. Задача

Кролики L09 зелёные за секунды. Исторический провал анализа был другим: ~4k tok промпта, TTFT ~80 с, reasoning съедал выход, один вызов требовал routing+slices+coverage+analysis.

Гипотезы W-очереди (не «выключить thinking» — это уже сделано):

1. На cpu-moe префилл 8k–16k может быть невыносим.  
2. Несколько YAML одним JSON тяжелее `hello.md`.  
3. «Сначала только routing» может проходить там, где naive dump нет.  
4. Минимальный агент (сам читает файлы) ближе к работе, чем дамп в user.

**SUT тот же:** `http://127.0.0.1:1240/v1`, `ornith-1.5-35b-a3b` Q4_K_M, `--reasoning off --ngl 99 --cpu-moe --ctx-size 33024 --parallel 4`. Studio `:1234` не входил. Если на медведе thinking=yes — не тот порт, не тюнить промпт.

---

## 2. Что оставить в вызове (итог)

| Режим | Когда | Timeout | Ориентир стены |
|---|---|---|---|
| `--suite rabbits` | Регрессия runtime | 180 с (избыточен) | 1–3 с / кейс |
| `analyze_route_only` | **Рабочий** шаг анализа | 300 с | cold ~13 с (~0.6k tok) |
| `intake_bundle` | Короткий intake, 2 файла | 300 с | cold ~18 с (~0.6k tok) |
| `analyze_naive` | Редкий полный срез | **600 с** | TTFT ~17 с, elapsed ~47 с (~3k tok) |
| `prefill_16k` | Тяжёлый шаг | **600 с** | TTFT ~41 с |
| `agent_loop.py` routing | Харнесс 4 JSON-инструментов | ≥300 с / ход | 7 ходов, ~23 с |

**Резать фазу, не железо:** даже при зелёном naive dump routing-only ~в 4 раза дешевле по стене. Не менять ngl / квант / модель, чтобы «ускорить dump».

**Не резать:** `--parallel 4`, ctx **33024**, 16k как размер тяжёлого шага. W05 (`--parallel 1`) = not-applicable: `prefill_8k` TTFT 22 с, не ≫ 30 с.

---

## 3. Цифры (thinking off, `finish=stop`, truncated 0)

Железо то же: RTX 4060 Laptop 8188 MiB, i7-12650H, 64 GB RAM, AC. VRAM на медведях **~5.2–5.4 / 8.2 GiB**. KV на cpu-moe почти не ест GPU (после лестницы 16k: 5195→5219 MiB).

### Префилл (W01)

| case | est tok | TTFT с | elapsed с |
|---|---:|---:|---:|
| prefill_4k | 4031 | 19.6 | 19.7 |
| prefill_8k | 8035 | 22.1 | 22.2 |
| prefill_16k | 16024 | 40.6 | 40.7 |

4k ≈ 8k по TTFT (первая ступень холоднее). 8k→16k ~1.8×. Это не исторические 80 с thinking-on.

### API-медведь (W02–W04)

| case | est tok | cold TTFT / elapsed | warm (×3) |
|---|---:|---|---|
| intake_bundle | 643 | 6.5 / 17.5 с | TTFT 0.15 с / ~12 с, 3/3 |
| analyze_route_only | 564 | 6.0 / 12.6 с | TTFT 0.15–0.46 с / ~7.3 с, 3/3 |
| analyze_naive | 3043 | 17.4 / **47.3 с** | один прогон, 4 файла, pass |

Naive TTFT рядом с `prefill_4k`, не с 16k. Генерация четырёх артефактов заметно длиннее TTFT — ждать до 600 с, не abort на 180.

Warm TTFT ~0.15 с — попадание в prefix cache того же промпта, не «префилл стал 150 мс».

### Агент (W06)

`python bench/agent_loop.py --case analyze_route_only`: list/read/write/done, без MCP и little-coder. **7 ходов, 22.8 с**, валидный `routing.yaml` (CR-001..003 → `inventory.stock`). vs W03 API cold 12.6 с.

Опциональный naive-агент: `ConnectionResetError`, процесс `:1240` умер. **not-tested**. Не повод ставить IntelliJ MCP.

Оракул агента сначала ложно валил прогон: seeded `request.md` содержит «Do not invent CR-004». Score теперь только `required_paths`.

### Регрессия кроликов на том же CLI

W00: 6/6, `files_payload` 1.14 с. W07 после рестарта сервера: 6/6, wall ~10.7 с, VRAM 5338 MiB.

---

## 4. Карточки (вердикты)

| ID | Вердикт | Одной строкой |
|---|---|---|
| W00 | pass | Кролики живы на frozen `:1240` |
| W01 | pass | Префилл 20/22/41 с; 16k рабочий; parallel не трогать |
| W02 | pass | Два файла change+request, без CR-004 |
| W03 | pass | Каталог+claims → только `routing.yaml` |
| W04 | pass | Dump четырёх файлов за 47 с; всё равно дороже routing |
| W05 | not-applicable | Триггер «8k ≫ 30 с» не сработал |
| W06 | pass | 4 инструмента закрывают routing; naive-агент не снят |
| W07 | pass | `workload-profile.yaml` + кролики 6/6 |

Ожидаемый исход «W03 pass + W04 fail → резать фазу» **не случился**: оба pass. Вывод тот же по стоимости: **сначала routing**. W03+W04 fail был бы про parse/промпт, не GPU.

---

## 5. Что не делать

- Studio `:1234` как SUT.  
- Abort 180 с на W04/префилл 16k.  
- `--parallel 1` «на всякий случай».  
- Ctx 8k / 262k; GPU-only 20 GiB на 8 GB.  
- Смена модели или более плотного кванта, пока нет новой боли сверх этих цифр.  
- little-coder / IDE MCP как норматив; W06 — профиль харнесса.  
- Holdout и skills соседних git root. Фикстуры — `inventory.stock`.  
- Переигрывать L00–L09.

---

## 6. Ограничения этой оценки

1. Синтетический склад, не прод-репо. Качество routing vs thinking-on **не** A/B.  
2. Warm цифры — cache того же промпта; холодный агент на новом контексте ближе к cold TTFT.  
3. nvidia-smi в `--nvidia` часто idle между кейсами, не пик префилла.  
4. Naive-агент не измерен; сервер один раз упал на первом ходе.  
5. `--json-schema` точечно на tool-ходы не снимали (L07: опционально, не global).  
6. Реальная обрезка tool-history / 10k+ чужого репо — вне этой папки.

---

## 7. Команды

```powershell
python bench/run.py --suite rabbits --base-url http://127.0.0.1:1240/v1
python bench/run.py --suite bear --base-url http://127.0.0.1:1240/v1
python bench/agent_loop.py --case analyze_route_only --base-url http://127.0.0.1:1240/v1 --timeout 300
```

Запуск сервера: тот же рецепт, что в кроличьем briefing / `experiments/L03-01/serve.py --no-mmproj --ngl 99 --ctx 33024 --cpu-moe`.
