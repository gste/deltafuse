# QF-012 — реальная reference qualification и закрытие

- **Приоритет:** P1
- **Зависимости:** QF-011 (инженерная переквалификация пройдена) и
  доступный LM Studio host с `ornith-1.5-35b-a3b`
- **Commit:** `release: record reference qualification`
- **Исходная работа:** [qualification-fix-plan.md, QF-012](../../qualification-fix-plan.md)
- **Статус до начала:** DF3-009 `blocked`; runs в release report — `pending`

Исполнитель: читай [README.md](../README.md). Пакет процедурный; главные
риски — соблазн подгонки. Правила ниже жёсткие.

## 1. Что делается

На референсном host выполняется кампания `scripts/qualify.py`:

```
python scripts/qualify.py --host lm-studio \
    --cases M01-cooldown M02-policy-stats M03-adversarial --runs 3
```

- модель `ornith-1.5-35b-a3b`, context 32768;
- cloud/mock fallback запрещён (инвариант раннера, QF-007);
- всего 9 независимых чистых прогонов (3 case × 3 run);
- thresholds T1–T8 применяются к каждому run и к медианам каждого case
  раннером автоматически; значения порогов не меняются.

## 2. Правила проведения (нарушение любого = кампания недействительна)

1. **Не выбирать лучший run.** Все 9 runs выполняются и публикуются;
   release report приводит все три результата каждого case.
2. **Не менять thresholds по результатам.** Любое ослабление — отдельный
   maintainer Decision с записью в
   [decisions.md](../../decisions.md) и новым `thresholds revision`; в
   рамках этого пакета запрещено.
3. **Чистый старт каждого run.** Раннер сам создаёт sandbox per run
   (`run_case`, staging из QF-004). Ручные правки sandbox между runs
   запрещены.
4. **Provenance.** Кампания запускается на чистом дереве (раннер
   fail-closed по dirty tree); commit/lock hash/thresholds revision
   фиксируются в manifest автоматически.
5. **Host доступен до старта.** Отказ host probe (`PENDING`, exit 2) — не
   ошибка кампании, а сигнал недоступности: никаких ретраев «подкрутить
   хост» без фиксации. Конфигурация LM Studio (context limit, model id)
   записывается probe'ом в manifest.
6. Если run/case упал (threshold failure или error-run) — фиксируется как
   есть; повторный прогон всего case допустим только как НОВАЯ кампания с
   новым campaign-id и полной публикацией обеих кампаний в release report
   (прозрачно, без удаления первой).

## 3. Порядок работ

1. Предпосылки: коммиты QF-001…QF-011 в ветке; `git status --porcelain`
   пуст; LM Studio запущен, модель загружена, context 32768.
2. Прогон команды кампании; наблюдение: host probe ok, staging per run,
   9 runs; вывод раннера сохранить целиком в RESULT.md.
3. После кампании: артефакты `bench/runs/<campaign-id>/` — manifest.yaml
   + 9 каталогов run (report.yaml + scorecard.yaml каждый). Сверить:
   schema-валидность (QF-008), все runs на месте, verdict каждого run и
   медиан вычислен раннером.
4. Скопировать фактические результаты в release report (раздел 2):
   таблица runs (все 9 verdicts), медианы correctness/process, provenance
   (campaign id, commit, lock hash, thresholds revision, host/model из
   manifest). Никаких ручных чисел — только копия из артефактов.
5. Если всё пройдено (каждый run, медианы correctness/process, T1–T8):
   отдельным commit закрыть программу:
   - `backlog/product/DF3-009.md`: статус `blocked` → `done`;
   - `backlog/product/v3/release-report.md`: статус → release/`passed`,
     раздел 4 закрытия заполнен фактическими значениями;
   - `backlog/product/index.md` и `backlog/product/deltafuse-3.md` —
     статус программы v3 (если там отражается DF3-009).
6. Если хотя бы один run/медиана не прошёл: результаты публикуются как
   есть, статус НЕ закрывается, finding в RESULT.md; программа остаётся
   открытой для maintainer-решения (thresholds менять нельзя).

## 4. Acceptance

- [ ] Сохранены все девять reports и campaign manifest (schema-valid).
- [ ] Каждый run, медианы correctness/process и T1–T8 проходят — только
      при этом условии закрытие.
- [ ] Release report содержит все три результата каждого case и
      provenance, а не только лучший.
- [ ] DF3-009, release report и программа переведены в `done` отдельным
      commit (при полном pass).
- [ ] Никакие thresholds не менялись; любые аномалии зафиксированы.

## 5. Evidence для RESULT.md

1. Команда кампании, campaign-id, дата, длительность.
2. Полный stdout раннера (host probe, runs, verdicts, medians, exit code).
3. `git rev-parse HEAD`; хост: model id, measured context (из manifest),
   LM Studio версия (если доступна), GPU/CPU (по возможности).
4. Листинг `bench/runs/<campaign-id>/` (manifest + 9 run-каталогов).
5. Итоговая таблица release report (раздел 2) после обновления.
6. Ссылка на закрывающий commit.

## 6. Commit

Один commit: `release: record reference qualification`.
Состав: `bench/runs/<campaign-id>/**` (артефакты), обновлённые
`backlog/product/v3/release-report.md`, `backlog/product/DF3-009.md`,
`backlog/product/index.md`, `backlog/product/deltafuse-3.md`, `RESULT.md`.

> Артефакты runs содержат полные tool-журналы; перед коммитом убедиться,
> что в них нет секретов/абсолютных путей окружения (правило AGENTS.md).
> Пути staging — temp-пути; при необходимости обезличить в RESULT.md,
> но не в машинных артефактах.
