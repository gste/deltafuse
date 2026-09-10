# Аппаратный и рантайм-профиль локальной модели (A03-03)

Исторический снимок Studio `:1234` / thinking on. **Текущий SUT A09:** [local-runtime](../local-runtime/README.md) (`:1240`, `--reasoning off`, `--cpu-moe`). Не запускать новые калибровки по этому файлу.

- **ID модели в LM Studio:** \ornith-1.5-35b-a3b\
- **Файл весов:** \D:\AI\models\lmstudio\ornith-ai\Ornith-1.5-35B-A3B-GGUF\Ornith-1.5-35B-Q4_K_M.gguf\
- **Размер файла:** 21,713,462,848 байт (~20.22 GiB)
- **SHA-256 весов:** \CA6EA26329C88B78FFD90A85163BE2E746C2FAFD1024F56DB47E499F117F9A7F\
- **Мультимодальный проектор (mmproj):** \D:\AI\models\lmstudio\ornith-ai\Ornith-1.5-35B-A3B-GGUF\mmproj-Ornith-1.5-35B-BF16.gguf\
- **Архитектура:** \qwen35moe\ (VLM / MoE)
- **Квантование:** \Q4_K_M\
- **Издатель / происхождение:** \ornith-ai\ / GGUF

## Runtime и бэкенд

- **Сервер / бэкенд:** LM Studio (\llama.cpp-win-x86_64-nvidia-cuda12-avx2-2.33.0\llama-server.exe\)
- **Порт прокси LM Studio:** \http://127.0.0.1:1234/v1\
- **Внутренний порт llama-server:** \127.0.0.1:61963\
- **Режим загрузки:** \mmap+mlock\
- **Шаблон чата:** Jinja (\chat-template.jinja\)
- **Speculative decoding:** Draft MTP (\--spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-n-min 0 --spec-draft-p-min 0.75\)

## Контекст и память

- **Максимальный контекст модели (max_context_length):** 262,144 токенов
- **Загруженный контекст (loaded_context_length / ctx-size):** 33,024 токенов (в командной строке: \--ctx-size 33000\)
- **KV Cache:** f16 (\--cache-type-k f16 --cache-type-v f16\), \--kv-offload\, \--kv-unified\, Flash Attention (\--flash-attn on\)
- **Батчинг:** batch-size 2048, ubatch-size 512, параллелизм 4 (\--parallel 4\), потоков CPU: 6 (\--threads 6\)

## Оборудование и распределение нагрузки (Offloading)

- **GPU:** NVIDIA GeForce RTX 4060 Laptop GPU (8188 MiB VRAM total, драйвер 616.56, CUDA 13.4)
- **Разделение слоёв (GPU vs CPU Offload):**
  - \--n-gpu-layers 27\: 27 слоёв выгружены на GPU.
  - Оставшиеся слои и веса исполняются на CPU с частичной фиксацией в RAM (\mlock\).
  - **Режим исполнения:** **CPU/GPU Hybrid Offload** (не является GPU-only, так как модель 20.22 GiB физически превышает 8 GiB VRAM).
  - VRAM использование под нагрузкой: ~7,482 MiB из 8,188 MiB (~91.4%).
- **CPU хоста:** 12th Gen Intel(R) Core(TM) i7-12650H (10 ядер, 16 логических процессоров)
- **RAM хоста:** 64 GiB (66,802,860 KiB total, ~9-10 GiB свободно при загруженной модели и приложениях)

## Тестовый пробный запрос

- **Эндпоинт:** \POST http://127.0.0.1:1234/v1/chat/completions\
- **Параметры:** \{"model": "ornith-1.5-35b-a3b", "messages": [{"role": "user", "content": "Respond with exactly: PING_OK"}], "max_tokens": 128, "temperature": 0.0}\
- **Длительность инференса:** 11.16 с (включая reasoning phase)
- **Сырой ответ:**
  \\\json
  {
    "id": "chatcmpl-4o3gmebbaceogwmdpu418j",
    "object": "chat.completion",
    "created": 1788667317,
    "model": "ornith-1.5-35b-a3b",
    "choices": [
      {
        "index": 0,
        "message": {
          "role": "assistant",
          "content": "PING_OK",
          "reasoning_content": "The user is asking me to respond with exactly \"PING_OK\". This appears to be a simple ping/pong style test, likely for connectivity or system checking purposes.\n\nI should just respond with exactly what they asked for.\n",
          "tool_calls": []
        },
        "logprobs": null,
        "finish_reason": "stop"
      }
    ],
    "usage": {
      "prompt_tokens": 17,
      "completion_tokens": 51,
      "total_tokens": 68,
      "completion_tokens_details": {
        "reasoning_tokens": 46
      }
    },
    "stats": {
      "total_draft_tokens_count": 16,
      "accepted_draft_tokens_count": 14,
      "rejected_draft_tokens_count": 2
    },
    "system_fingerprint": "ornith-1.5-35b-a3b"
  }
  \\\
- **Наблюдение:** Модель генерирует reasoning-токены (\easoning_content\, 46 токенов) перед финальным контентом (\PING_OK\, 5 токенов). При установке слишком малого \max_tokens\ (например, 16) лимит токенов исчерпывается на reasoning-фазе, и финальный контент остаётся пустым со статусом \inish_reason: length\. Для задач анализа и генерации необходим достаточный резерв токенов генерации (>= 1024-2048).