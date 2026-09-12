# QF-012 — результат исполнения (reference qualification)

- **Статус:** НЕ ВЫПОЛНЕНО — заблокировано недоступностью reference host
- **Commit:** `ba4e3eb3e47af7c7d7970a9774d88a03fd7dbbe2` (QF-011)
- **Дата:** 2026-09-12

## Что произошло

Reference host (LM Studio, `http://127.0.0.1:1234`, модель
`ornith-1.5-35b-a3b`, context 32768) недоступен на машине разработки.
Кампания запущена официально; раннер ответил fail-closed `PENDING` (exit 2):

```
python scripts/qualify.py --host lm-studio --cases M01-cooldown M02-policy-stats M03-adversarial --runs 3
framework commit: ba4e3eb3e47af7c7d7970a9774d88a03fd7dbbe2
framework lock: sha256:a562f62d52a7...
thresholds revision: a170fc800423
PENDING: host probe failed: <urlopen error [WinError 10061] Подключение не установлено ...>
Qualification runs are not executed and no results are fabricated.
campaign rc=2
```

Никакие runs не выполнялись; ни один результат не синтезирован
(прямое требование плана: «Отсутствие LM Studio не мешает исправить
QF-001–QF-011 и не разрешает синтетически заполнять результаты reference
runs»).

## Состояние программы

- DF3-009 остаётся `blocked`; release report остаётся
  `engineering-passed / pending reference runs`; таблица runs — `pending`.
- Закрытие программы (commit `release: record reference qualification`,
  перевод DF3-009/release report/программы в `done`) возможно только после
  фактической кампании: LM Studio + `ornith-1.5-35b-a3b`, context 32768,
  9 прогонов, T1–T8 по каждому run и медианам, публикация всех артефактов
  `bench/runs/<campaign-id>/`.

## Как возобновить

1. Запустить LM Studio с загруженной `ornith-1.5-35b-a3b`, context 32768.
2. На чистом дереве: `python scripts/qualify.py --host lm-studio --cases
   M01-cooldown M02-policy-stats M03-adversarial --runs 3`.
3. Далее по INSTRUCTION.md §3 (публикация артефактов, обновление release
   report, закрывающий commit при полном pass).
