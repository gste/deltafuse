# DeltaFuse 3.0 — завершение программы

- **Статус:** `active`
- **Версия:** `3.0.0`
- **Текущий план:**
  [v3/qualification-fix-plan-wave-2.md](v3/qualification-fix-plan-wave-2.md)
- **Предыдущий fix plan:** [v3/qualification-fix-plan.md](v3/qualification-fix-plan.md)
- **Исходный completion plan:** [v3/completion-plan.md](v3/completion-plan.md)
- **Release qualification:** [DF3-009](DF3-009.md)

Базовая реализация v3 находится в коде. Программа не считается завершённой,
пока qualification runner не измеряет T1–T8 без обходов, Worker-контракты не
проходят сквозной процесс, а три чистых прогона M01, M02 и M03 на reference
35B A3B Worker не достигнут абсолютных порогов.

## Неизменяемая рамка

- Lifecycle: `Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`.
- Reference lower bound: локальная LLM класса 35B A3B.
- Полное окно Worker: 32k токенов; framework-controlled input: не более 16k
  токенов и 24 уникальных файлов на вызов.
- Core владеет переходами, evidence stamps и receipts; Worker не меняет эти
  состояния вручную.
- Human Gates: Decision, specification acceptance и merge.
- Поддерживаются nested source checkout и wheel без зависимости wheel от
  исходного checkout.
- Совместимость и qualification v2 не входят в программу.

## Definition of Done

1. Все пункты
   [qualification fix plan wave 2](v3/qualification-fix-plan-wave-2.md)
   закрыты проверяемыми тестами.
2. Полный pytest, PowerShell/POSIX smoke, wheel smoke и layout validation зелёные.
3. Девять реальных qualification-прогонов сохранены с полным provenance.
4. Каждый прогон и медианы удовлетворяют T1–T8 из [thresholds.md](v3/thresholds.md).
5. [release-report.md](v3/release-report.md) имеет `verdict: pass`, после чего
   DF3-009 и программа переводятся в `done`.
