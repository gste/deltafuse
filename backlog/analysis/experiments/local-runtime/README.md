# Локальный runtime для аудита DeltaFuse (A09)

Дата фиксации: 2026-09-06. Это **текущий** SUT калибровки A09, не исторический снимок A03-03 (LM Studio `:1234`, thinking on).

Оптимизация L00–W07 закрыта. Новый bear-bench не нужен, пока A09 не покажет другую боль. Качество claims/гейтов на S02 этот файл не заменяет.

## Железо (минимум, как у калибровки)

| Ресурс | Факт калибровки |
|---|---|
| GPU | RTX 4060 Laptop **8 GB** (слабее не рассматривали) |
| RAM | **64 GB** (веса Q4 ~20 GiB + mmap) |
| CPU | i7-класса, hybrid MoE: эксперты в RAM, dense/attn на GPU |
| GPU-only 35B Q4 на 8 GB | **невозможен** |

Питание от сети, NVIDIA Performance. На батарее цифры врут.

## Модель

- ID: `ornith-1.5-35b-a3b`
- Файл: `Ornith-1.5-35B-Q4_K_M.gguf` (~20.22 GiB)
- SHA-256: `CA6EA26329C88B78FFD90A85163BE2E746C2FAFD1024F56DB47E499F117F9A7F`
- Архитектура: `qwen35moe` (VLM/MoE). **mmproj не грузить** (текст).
- Путь к GGUF — локальный; в артефактах писать `weights-root/...`, не username.

## Запуск (голый llama-server, не прокси Studio)

Бинарник калибровки: LM Studio CUDA `llama.cpp-win-x86_64-nvidia-cuda12-avx2-2.33.0` `llama-server.exe`. Тот же файл можно запускать **без** OpenAI-прокси Studio.

Studio `:1234` **не** SUT: прокси отбрасывает thinking-off kwargs. Endpoint: **`http://127.0.0.1:1240/v1`**.

CUDA vendor DLL (`backends/vendor/win-llama-cuda12-vendor-v2`) должна быть в `PATH`, иначе Windows `0xC0000135`.

```powershell
$env:ORNITH_GGUF = "weights-root\ornith-ai\Ornith-1.5-35B-A3B-GGUF\Ornith-1.5-35B-Q4_K_M.gguf"
# optional: $env:CUDA_VENDOR = "...\backends\vendor\win-llama-cuda12-vendor-v2"
.\serve.example.ps1
```

Проверка: `GET http://127.0.0.1:1240/v1/models` — в списке `ornith-1.5-35b-a3b`. Ping `PING_OK` без `reasoning_content`.

Без `--api-key`. JSON Schema не на весь сервер.

## Клиент (A09 harness)

```powershell
$env:DELTAFUSE_LLM_URL = "http://127.0.0.1:1240/v1/chat/completions"
# thinking off на сервере (--reasoning off); не слать enable_thinking: true
python backlog/analysis/experiments/A09-01/harness/run_case.py --case S02 --repeat 1 --phase analyze
```

По умолчанию Analyze пишет **только** `routing.yaml` (`A09_ANALYZE_FOCUS=routing`). Полный дамп: `A09_ANALYZE_FOCUS=full` (timeout до 600 с).

## Бюджеты (измеренные, thinking off)

| Вызов | Timeout | Ориентир стены |
|---|---|---|
| Короткий JSON / routing / intake | 300 с | cold ~7–18 с; warm cache того же промпта не обобщать |
| Полный Analyze-dump / префилл ~16k | 600 с | dump ~47 с; 16k TTFT ~41 с |
| Пакет Change | 30 мин | снова реалистичен, если фазы нарезаны |
| `max_tokens` | 2048 на шаг | 8192 — запас, если снова `length` |
| Окно сервера | **33024** | файл-бюджет слайса 16k; 8k окно для агентов мало |
| `--parallel` | **4** | не менять «на всякий случай» |

16k — размер **редкого** полного среза, не каждого хода. Сначала маленький артефакт (routing), не весь Analyze одним JSON.

## Харнесс агента

Калибровка: файлы + JSON `files[]` или 4 файловых инструмента. IDE MCP / little-coder не норматив A09. Если процесс `:1240` падает на длинном tool-loop — рестарт сервера, мельче фаза.

## Источники

- Исторический Studio-снимок: [A03-03/profile.md](../A03-03/profile.md)
- Кролики: [OPTIMIZATION-BRIEFING.md](../../../OPTIMIZATION-BRIEFING.md)
- Медведи: [OPTIMIZATION-BRIEFING-BEARS.md](../../../OPTIMIZATION-BRIEFING-BEARS.md)
- F-007 (thinking съедает 2048): [F-007.md](../../../findings/F-007.md) — mitigated этим профилем
