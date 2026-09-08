# Результат эксперимента A12-01

- **ID карточки:** A12-01
- **Ревизия старта:** `72a80a8`
- **Статус исполнения:** **done**
- **Критерии:** все IDs [criteria.md](../../../criteria.md) + BASE-001..005; контроль [плана §5](../../../analysis-plan.md)
- **Вердикт:** **pass** — покрытие сведено; пробелы помечены `not-tested`; findings отделены от Q-*. Четыре исходных вопроса **не** отвечались (это A12-02).

## Гипотеза

Каждый критерий и каждая фаза уже имеют согласованный вердикт; очередь без скрытых blocked; A01-pass можно читать как «DF соответствует критерию».

**Альтернатива:** A01-pass — только дефиниция. Framework-pass и SUT-fail живут на разных слоях (F-010, F-009, F-005). Verify/Archive, interrupt, analog live, F-006 на SUT — **not-tested**, не pass.

Привязка: A09-13, A10-02, A11-06; index `blocked=0`.

## Ожидаемое

Индекс: критерий/фаза → verdict + evidence или причина not-tested; findings ≠ гипотезы; противоречия разрешены по первичным данным; blocked не скрыты.

## Наблюдаемое

Матрица: [coverage.md](../../matrices/coverage.md).

- A01 `pass` ≠ соответствие продукта.
- Главный SUT-стоп: F-010 Specify; 11/11 holdout fail; 0 `converged`.
- Framework-fail с finding: F-001…F-006, F-008…F-010. F-007 mitigated на `:1240`.
- Analog quality **not-tested** (A11-06). Homemade SDD A10-01 не подменять аналогом.
- Q-001…Q-008 остаются гипотезами до A12-04.
- `blocked` карточек нет. Mock не выдавался за ornith.

## Ограничения

Не новый LLM-прогон. Не roadmap (A12-03). Не ответы на 4 вопроса (A12-02). Packet path `analysis/criteria.md` отсутствует.

## Handoff

- **Готово A12-01:** `done` / `pass` (полнота покрытия). Дальше [A12-02](../../packets/A12-02.md).
- A12-02: только слои из coverage.md; не поднимать analog vs ornith; не лечить F-007.
- A12-04: parking Q-*; A12-03: P0 F-010/F-009/F-004/F-006, не усреднять score.
- Skills / integrity не патчить.
