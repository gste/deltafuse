# Контракт снимка доски (DeltaFuse ↔ fuse-map)

[English](board-snapshot.md) | [**Русский**](board-snapshot.ru.md)

Машинная схема: [board-snapshot.schema.yaml](board-snapshot.schema.yaml) (`schema_version: 1`).

**Канон продюсера** — этот репозиторий. fuse-map пинит тот же `schema_version` у себя в `docs/contracts/`. SSOT артефактов — git продукта. Снимок — только чтение.

CLI/API появятся в [FM-001](../../backlog/product/FM-001.md) (отдельная ветка). Документ уже является pin совместимости.

## Роли

| Сторона | Репозиторий | Обязанность |
|---|---|---|
| Продюсер | DeltaFuse | Отдать снимок по схеме. Не писать файлы продукта, пока строит снимок. |
| Потребитель | fuse-map | Рисовать карточки только из снимка. Не делать хранилище UI истиной Change. |
| Склад | git продукта | `docs/changes/**`, архив, spec, Decisions. |

Продукт DeltaFuse = читаемый `.deltafuse/lock.yaml`. Нет lock — жёсткая ошибка, не пустая доска.

## Транспорт

```text
deltafuse board <product-root> --json
deltafuse board <product-root> --json --archive
```

Stdout при `--json` — ровно один JSON (UTF-8); диагностика в stderr. Успех: exit `0`. Не продукт / битый lock: exit `≠ 0`, без «почти доски». Корни Changes — из `paths.changes` / `paths.archive` в config. Ноль записи на диск. `check-gate` на каждый CHG в v1 не гонять.

## Совместимость

`schema_version` снимка **не** равен `schema_version` у `change.yaml` (там `2`).

Новое опциональное поле — остаётся `1`; потребитель игнорирует неизвестные ключи. Переименование / удаление / смена типа обязательного поля — bump на `2`. Неизвестный `schema_version` у потребителя — явный fail этого репо, не сканер YAML.

## Запреты

Потребитель: не парсить `change.yaml` как контракт, когда есть `board`; не писать артефакты Change; не прятать `warnings`. Продюсер: не класть тела spec/request в JSON; не индекс-файл в продукте; не HTTP-демон в v1.

Пример JSON — в [английской версии](board-snapshot.md).
