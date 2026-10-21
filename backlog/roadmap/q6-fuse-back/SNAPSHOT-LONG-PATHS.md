# q6: снимок `declaring` (3.3.8) удлиняет пути — на Windows `git add` падает без `core.longpaths`

**Состояние: сделано 2026-10-21 (вариант 1 - хранилище по хэшу, плюс вариант 3), ветка `fix/fuseback-338`.** Копия снимка - `.deltafuse/snapshots/<sha256>` (85 символов от корня продукта при любой глубине пути), квитанция `{путь: sha256}` находит её при переоткрытии; копии 3.3.8 в старой раскладке читаются. README (en, ru) называет `git config core.longpaths true` для продуктов с глубокими путями; ядро настройку git не меняет. Было: наблюдение, к разбору. Записано 2026-10-21 по проверке 3.3.8 (`aa92be6`) на Gradle-варианте J01 после
Fuse-Back (`fuseback/docs/planning/E2E-CHANGE-J03.md`, «Седьмой прогон»).

## Что произошло

Шлюз `declaring` копирует файлы продукта задачи в `.deltafuse/snapshots/<change>/<путь>`. В `allowed_paths` был
характеризующий тест Fuse-Back
`src/test/java/fuseback/characterization/traffic_management/rate_limiting/TokenBucketLimiterCharacterizationTest.java`;
его снимок — 104 символа от корня продукта, 236 абсолютный путь. `git add -A` на Windows без `core.longpaths true`:

```
error: open(".deltafuse/snapshots/CHG-001-negative-amount/src/test/java/fuseback/characterization/..."): Filename too long
fatal: adding files failed
```

Шлюз прошёл, но коммит шага — нет. В многомодульном проекте (`<module>/src/test/java/...`) путь ещё длиннее.

## Варианты (решение владельца)

1. Короче префикс снимка (например `.deltafuse/s/<короткий id>/`) или снимок по хешу содержимого с картой путей в
   квитанции вместо зеркала дерева.
2. `deltafuse init` на Windows проверяет `core.longpaths` и предупреждает (или включает в репозитории продукта).
3. Документировать требование `core.longpaths` для Windows.

Fuse-Back со своей стороны просит включить `core.longpaths` в README.
