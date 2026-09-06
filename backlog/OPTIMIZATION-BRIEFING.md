# Ornith локально: выводы очереди оптимизации

Канонический запуск в репозитории DeltaFuse: [analysis/experiments/local-runtime/README.md](analysis/experiments/local-runtime/README.md).

Дата: 2026-09-06. Репозиторий `llm-optimization`, очередь L00–L09 **закрыта**.  
Норматив измерений: portable bench (`ping`, `json_min`, `files_payload`, `extract_claims`, `ignore_injection`, `five_words`). Не агентный workflow по репо.

Этот файл — сводка для внешнего анализа следующих шагов. Сырьё: `experiments/Lxx-01/result.md`, `experiments/bench-runs/`, `experiments/L09-01/frozen-profile.yaml`.

---

## 1. Задача и машина

**Цель.** Сделать `ornith-1.5-35b-a3b` (Qwen3.5-family MoE, VLM, Q4_K_M ~20.22 GiB) пригодной для коротких JSON/chat-вызовов на ноутбуке, без смены модели «ради 1%».

**До очереди (факты, не гипотезы).** Модель JSON **умеет**. Узкое место — thinking: при включённом `<think>` `max_tokens: 2048` часто даёт пустой `content` (`finish_reason: length`); валидный маленький `{files,status,notes}` занял **1177 с** и ~15k символов reasoning. Top-level `"enable_thinking": false` и `/no_think` **не** выключали reasoning.

**Железо.** RTX 4060 Laptop **8 GB** (nvidia-smi ~8188 MiB), i7-12650H (10C/16T), **64 GB RAM**, Windows, питание AC. GPU-only 20 GiB Q4 на 8 GB **невозможен**. Официальный serving Ornith — 2×80 GB; локально это гибрид RAM+GPU.

**SUT.** LM Studio llama.cpp CUDA `2.33.0` (`llama-server.exe`), затем тот же бинарь голый. Endpoint frozen: `http://127.0.0.1:1240/v1`. Studio OpenAI `:1234` в профиль **не входит**.

**Модель.** ID `ornith-1.5-35b-a3b`, SHA-256 GGUF `CA6EA26329C88B78FFD90A85163BE2E746C2FAFD1024F56DB47E499F117F9A7F`. Это **гибридный thinking**-модель (явный CoT в токенах), не отдельный «внутренний ризонер». `--reasoning off` = не генерировать think-токены; способность рассуждать в весах остаётся.

---

## 2. Замороженный рецепт (итог)

Живой профиль: `experiments/L09-01/frozen-profile.yaml`.

```text
llama-server \
  --model <Q4_K_M.gguf> --alias ornith-1.5-35b-a3b \
  --host 127.0.0.1 --port 1240 --no-webui --jinja \
  --reasoning off \
  --ctx-size 33024 \
  --n-gpu-layers 99 --cpu-moe \
  --split-mode layer --ctx-checkpoints 32 \
  --batch-size 2048 --ubatch-size 512 \
  --threads 6 --parallel 4 \
  --cache-type-k f16 --cache-type-v f16 \
  --flash-attn on --kv-offload --kv-unified --load-mode mmap+mlock \
  --spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-n-min 0 --spec-draft-p-min 0.75
```

- mmproj **не** грузить для текста.  
- CUDA DLL: `.../backends/vendor/win-llama-cuda12-vendor-v2` в `PATH`, иначе `0xC0000135`.  
- Без `--api-key`.  
- JSON Schema **не** на весь сервер; опционально в теле JSON-запроса (`experiments/L07-01/`).

**Полный bench на этом профиле (L09):** 6/6, thinking off, ни одного `length`. `files_payload` **1.96 с** (было 1177 с). Warm ping **0.23–0.33 с**. VRAM ~**4920 / 8188 MiB**. RAM процесса ~**21 GB** (mmap+mlock).

Честный timeout на JSON-кейсы bench — **секунды**, не 180 и не 900.

---

## 3. Что дало эффект (по силе)

### 3.1 Thinking off — главный выигрыш

- Jinja Ornith ветвит по `enable_thinking`.  
- Top-level `enable_thinking: false` **игнорируется** и Studio, и native llama-server.  
- `chat_template_kwargs.enable_thinking=false` работает на **native** порту llama-server; **прокси Studio `:1234` поле отбрасывает** (тот же процесс, тот же GGUF: 4.57 с и 17 reasoning tokens vs off).  
- Frozen: CLI `--reasoning off` (бинарь помечает kwargs как deprecated).  
- Ping: ~4.2 с (thinking on, Studio) → ~0.7 с (kwargs native) → ~0.2 с (полный frozen).

Это не «включить внутренний reasoning». Это не платить think-токенами. Для агентного кода community-замер Ornith 1.0: thinking-on не поднял coding-скор.

### 3.2 `--cpu-moe` + `--ngl 99` — главный VRAM/скорость после thinking

Сравнение на ctx 33024, thinking off (L05):

| | ngl 27, эксперты с слоями | `--ngl 99 --cpu-moe` |
|---|---|---|
| Warm ping | 0.59 с (~5 tok/s) | **0.28 с (~10.7 tok/s)** |
| VRAM | 7704 / 8188 | **4838 / 8188** |
| RAM WS | ~22.9 GiB | ~21.1 GiB |

Эксперты MoE в RAM, dense/attn на GPU. L03 «добавить ngl при layer-split» VRAM почти не менял (~7.6 GB всегда): карта была забита не KV, а размещением экспертов.

### 3.3 Голый llama-server, не Studio UI

Тот же CUDA-бинарь 2.33.0. Ping не лучше native-порта Studio, но нужны CLI (`--cpu-moe`, `--reasoning off`) и отсутствие фильтра полей. Порт **1240**, не 1234.

### 3.4 Мелочи

- **Без mmproj** (текст): warm ping чуть лучше, VRAM в nvidia-smi не освободилась.  
- **MTP on** (`draft-mtp` n-max 2): ping на ~0.04–0.08 с быстрее off; `files_payload` в шуме; off экономит ~0.9 GiB VRAM. Оставили on. Статы `accepted_draft_tokens` в chat `usage` нет.  
- **JSON schema** per-request работает; unconstrained после thinking-off уже закрывает `files_payload` за **23** completion tokens. Глобальная grammar сломает ping.

---

## 4. Что не сработало / отвергнуто

| Рычаг | Факт |
|---|---|
| Top-level `enable_thinking` | Молча no-op |
| `/no_think` (до очереди) | Content есть, reasoning остаётся |
| Больше ngl без `--cpu-moe` | ngl 28…99 влезает, VRAM/ping не растут |
| `--parallel 1` при ctx 33k | Ping хуже (~0.77 с vs ~0.50) |
| KV `q8_0` | Ping хуже (~0.91 с), VRAM не отдали |
| `--threads 10` | Чуть хуже threads 6 на коротком ping |
| ctx 8k как «быстрее» | Bench JSON ок с 4k; **агенты на проектах 8k съедают и падают**. На 4060 4k/8k/16k/33k VRAM **одинаковая** (~7.6 GB до cpu-moe). Рабочий ctx **33024**. 262k не трогали |
| Более плотный квант (L08) | Триггер не сработал (ping ≪ 5 с, files ≪ 60 с). Другого GGUF локально нет. Остались Q4_K_M |
| Другая модель (bonsai / qwen3.6 sibling) | Сознательно не A/B |
| vLLM / ik_llama.cpp | Вне скоупа |
| NVIDIA «Prefer Max Performance» | В реестре пусто; Windows только Balanced |

WDDM: per-process GPU memory часто `[N/A]`. Смотреть суммарную VRAM.

---

## 5. Карточки (вердикты)

| ID | Вердикт | Одной строкой |
|---|---|---|
| L00 | pass | Baseline Studio: ping 4.1–6.7 с, thinking on, VRAM ~7.7/8.2 GiB, AC, cmdline ngl 27 / ctx 33k / MTP |
| L01 | pass | Thinking-off только native llama-server + kwargs; Studio proxy врёт |
| L02 | pass | База = голый server `:1240`, тот же бинарь |
| L03 | partial | Упаковка слоёв/KV/parallel не ускорила; узкое место не «мало ngl» |
| L04 | pass | Bench ок с 4k; операционный ctx 33k (агенты) |
| L05 | pass | `--cpu-moe` + ngl 99 |
| L06 | pass | MTP оставить |
| L07 | pass | Schema опциональна, не в global frozen |
| L08 | not-applicable | Не качать Q3 |
| L09 | pass | Frozen + bench 6/6 |

---

## 6. Ограничения этой оценки

1. Bench — короткие синтетические кейсы. **Не** измерялись длинные агентные сессии, tool-loops, чтение репо, 10k+ prompt. Хозяин машины: на проектах 8k контекста агенты забивают. 33k выбран как «бесплатный» запас на этой карте, не как доказанный потолок для агентов.  
2. tok/s ~11–25 на JSON / ~11 на warm ping cpu-moe — для интерактивного агента с большим prompt будет хуже (префилл на CPU-экспертах).  
3. `--parallel 4` оставлен с baseline; для одного агента не перепроверяли после cpu-moe.  
4. Качество vs thinking-on на сложных задачах **не** A/B (только latency/parse).  
5. Stream `usage` часто пустой — thinking смотреть по `reasoning_content`.  
6. LM Studio без загруженной модели ~400 MB RAM; VRAM держит llama-server.

---

## 7. Вопросы на следующие шаги (не очередь L00–L09)

Имеет смысл анализировать **вне** этой папки:

1. **Интеграция агентов** на `:1240` (не Studio). Нужен ли обёртка-прокси, который всегда шлёт thinking-off, если кто-то снова пойдёт в `:1234`?  
2. **Реальный агентный ctx:** 33k vs обрезка tool-history vs summarization. Bench этого не ловит.  
3. **Префилл** на больших промптах (cpu-moe): измерить TTFT на 4k/8k/16k prompt, не на ping.  
4. `--parallel 1` **после** cpu-moe (в L03 parallel 1 мерили на другом offload).  
5. Точечный `--json-schema` только на tool/JSON-ходы агента.  
6. Нужен ли ещё tok/s (ik_llama, другой квант) — только если агентный префилл невыносим; L08 порог по bench уже пройден.  
7. Запуск после ребута: скрипт + CUDA vendor PATH; оркестрация с Cursor/прочим клиентом.

Не рекомендуется без новой боли: смена модели, 262k ctx, GPU-only обещания, бесконечный ngl-тюнинг.
