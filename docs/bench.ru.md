# Бенчмарки и оценка воркеров

Набор бенчмарков, сценарии тестирования (`J01`, `J03-document-flow`, `M01-M03`), квалификационный харнесс, мутационные судьи и автономные супервизоры вынесены и поддерживаются в отдельном репозитории:

👉 **[gste/deltafuse-bench](https://github.com/gste/deltafuse-bench)**

## Обзор

`deltafuse-bench` измеряет качество следования процессу **DeltaFuse** (`Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`) и корректность реализации интеграционных требований для автономных ИИ-агентов и разработчиков.

### Установка и запуск

```bash
# Клонирование и установка бенчмарка
git clone https://github.com/gste/deltafuse-bench.git
cd deltafuse-bench
pip install -e .

# Развертывание чистой песочницы
deltafuse-bench install /path/to/sandbox --force

# Запуск сквозного прогона под управлением супервизора
deltafuse-bench supervise /path/to/sandbox --little-coder --model poolside/laguna-xs-2.1

# Оценка результатов и сбор evidence
deltafuse-bench run --run-id run-01 --sandbox /path/to/sandbox --out /path/to/evidence
```

Подробную документацию по структуре кейсов, метрикам и методологии скоринга см. в репозитории [gste/deltafuse-bench](https://github.com/gste/deltafuse-bench).
