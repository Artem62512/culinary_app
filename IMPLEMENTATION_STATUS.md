# Culinary App — implementation status

## Current scope

The project is being adapted to a single-owner application. Registration, multiple accounts, roles, public/private recipe visibility, copying recipes between users, and moderation workflows are out of scope.

## Completed in this working copy

1. Extracted the supplied archive into a separate working directory. The uploaded RAR archive was not modified.
2. Did not copy the archive's `.env` file. Use `.env.example` to create a local `.env` and enter the owner's credentials locally.
3. Created a verified SQLite backup at `backend/backups/culinary.db.before_single_user.bak` before applying the migration.
4. Added Alembic configuration and an initial data migration `0001_single_owner`.
5. The migration requires exactly one row in `users` and assigns existing recipes with `user_id IS NULL` to that owner. It does not change recipe IDs, recipe content, ingredients, products, prices, or shopping lists.
6. Centralized the single owner's ID as `OWNER_ID = 1` and applied it when creating new recipes and shopping lists.
7. Fixed the pytest discovery issue: tests are restricted to `backend/tests`.
8. Made `backend/scripts/smoke_test.py` safe to import; it no longer inserts a product as a side effect.

## Database state after migration

- `users`: 1
- `recipes`: 6
- `recipe_ingredients`: 18
- `products`: 85
- `product_prices`: 10
- `shopping_lists`: 16
- `shopping_list_items`: 30
- All 6 recipes have `user_id = 1`.
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: no violations.
- Alembic revision: `0001_single_owner`.

## Tests

- Backend pytest suite: 14 passed.
- The test runner no longer imports scripts from `backend/scripts` as tests.
- Frontend build was not run because `npm ci` could not fetch a package from the npm registry in this environment (`EAI_AGAIN`). No partial `node_modules` directory is included.

## Important implementation notes

- Authentication remains the existing single-owner HTTP Basic mechanism configured by `APP_USERNAME` and `APP_PASSWORD`. Registration and multi-user auth have not been introduced.
- The `users` row is retained because existing foreign keys use it. It represents the one owner and is not a registration system.
- The existing `main.py` still uses `Base.metadata.create_all()` for bootstrap compatibility. New schema changes should be introduced through Alembic migrations; a later phase should replace implicit startup schema changes with an explicit bootstrap/migration workflow once a complete baseline migration exists.
- The original uploaded archive and its database were not modified.

## Next work

1. Add recipe editing (`PUT`/`PATCH`) while preserving recipe IDs and ingredient relationships.
2. Add safe deletion/undo behavior and complete shopping-list item updates.
3. Expand product catalog management, categories, synonyms, and unknown recipe ingredients.
4. Improve nutrition calculations and partial-value display.
5. Implement recipe search and ingredient-based matching.
6. Implement recipe text parser that fills the existing form without auto-saving.
7. Add store adapters only after verifying actual permitted data sources.

## Этап 2. Редактирование рецептов

Реализовано после этапа безопасной миграции:

- Добавлен `PUT /api/recipes/{recipe_id}` с полной валидацией состава до изменения записи.
- Обновление сохраняет ID рецепта и `created_at`; обновляет название, описание, число порций, инструкцию и список ингредиентов.
- Для неизвестного `product_id` возвращается 404 до изменения данных рецепта.
- При ошибке записи выполняется rollback.
- Форма рецепта переиспользуется для создания и редактирования; существующие продукты подгружаются по ID, состав и примечания восстанавливаются.
- Добавлена возможность менять краткое описание и примечание каждого ингредиента.
- В просмотре рецепта появилась кнопка «Редактировать».
- В `ProductOut` добавлены `base_name` и `variation`, чтобы форма корректно восстанавливала группу/вариант существующего продукта.
- Добавлены тесты обновления, сохранения исходных данных при ошибке и 404 для отсутствующего рецепта.

Проверки после изменений:

- `pytest -q`: 17 passed.
- `python -m compileall -q app tests`: успешно.
- Основная SQLite база: 1 пользователь, 6 рецептов, 18 ингредиентов рецептов, 85 продуктов, 10 цен, 16 списков покупок, 30 элементов списков.
- `PRAGMA integrity_check`: `ok`; `PRAGMA foreign_key_check`: нарушений нет.
- Перед этим этапом создана копия `backend/backups/culinary.db.before_recipe_edit.bak`.
- Полная сборка frontend пока не подтверждена: `node_modules` отсутствует, установка зависимостей ранее завершилась сетевой ошибкой DNS (`EAI_AGAIN`). Глобальный TypeScript-компилятор доступен, но без локальных зависимостей и типов React полноценная проверка проекта невозможна.

## Этап 3. Каталог продуктов — базовая структура и интерфейс

Реализовано:

- Добавлена отдельная таблица `product_categories` с 13 категориями из технического задания: овощи; фрукты и ягоды; мясо; птица; рыба и морепродукты; молочные продукты; яйца; крупы и макаронные изделия; бобовые; хлеб и выпечка; орехи и семена; соусы и специи; другое.
- В `products` добавлено nullable-поле `category_id` с внешним ключом. Старое текстовое поле `category` сохранено для обратной совместимости.
- Все 85 существующих продуктов привязаны к одной из 13 категорий. Названия, ID, КБЖУ, источники, цены и ссылки рецептов не менялись.
- Добавлена таблица `product_aliases`. Синонимы нормализуются без учёта регистра, `ё/е`, лишних пробелов и пунктуации; один нормализованный синоним нельзя закрепить за несколькими продуктами.
- Добавлен поиск по названию и синонимам, фильтр по категории, API просмотра/добавления/удаления синонимов и API списка/создания категорий.
- Добавлена вкладка «Каталог продуктов»: просмотр, поиск, фильтрация, добавление продукта, просмотр и управление синонимами.
- В форме рецепта поиск групп продуктов учитывает синонимы; старые рецепты получают отображаемое имя нормализованной категории без изменения старого текстового значения.
- Добавлена защита от новых продуктов с уже существующим нормализованным названием.

Сохранность и проверки:

- Перед миграцией создана копия `backend/backups/culinary.db.before_product_catalog.bak`.
- Миграция `0002_product_catalog` проверена как на рабочей базе, так и на отдельной копии базы с предыдущей ревизией.
- `pytest -q`: 25 passed.
- `python -m compileall -q app tests`: успешно.
- SQLite `integrity_check`: `ok`; `foreign_key_check`: нарушений нет.
- Основные таблицы сохранили прежнее число записей: users 1, recipes 6, recipe_ingredients 18, products 85, product_prices 10, shopping_lists 16, shopping_list_items 30.
- Добавлено 13 категорий; все 85 продуктов получили category_id; таблица синонимов пока пустая, так как автоматическое назначение неоднозначных синонимов могло бы подменять разные продукты.
- Найдены старые дубли названия «Мука пшеничная в/с» (ID 31, 81–85). Они не объединялись: у них различаются значения КБЖУ. Ни одна запись не удалена.
- Полная сборка frontend не подтверждена: в архиве отсутствуют `node_modules`, установка зависимостей ранее не прошла из-за сетевой ошибки DNS. Повторная проверка TypeScript также остановилась на отсутствующих React и других npm-зависимостях.

Ограничения текущего этапа:

- Категории и синонимы готовы как структура и API; безопасное автоматическое наполнение каталога новыми продуктами не выполнялось без подтверждённых источников данных.
- Разделение универсальных ингредиентов и конкретных товаров магазинов, массовое сопоставление и объединение дублей требуют отдельного этапа. Существующие связи рецептов и цен пока оставлены без изменений.
- Модерация и подтверждение изменений не добавлялись: приложение остаётся однопользовательским, изменения владельца сохраняются напрямую.

## Следующие задачи

1. Добавить неизвестные ингредиенты, которые можно сохранить только в конкретном рецепте, не создавая фиктивный продукт в общем каталоге.
2. Спроектировать безопасное разделение универсальных продуктов и магазинных товаров с сохранением текущих ссылок и цен.
3. Добавить управляемое сопоставление и объединение дублей с предварительным просмотром влияния на рецепты и цены.
4. Затем перейти к точности расчёта КБЖУ и частичным данным.


## Этап 4. Неизвестные ингредиенты — выполнено

Реализовано:

- В `recipe_ingredients` поле `product_id` стало nullable; добавлены `custom_name`, `matching_status`, `matched_product_id`.
- Добавлена миграция Alembic `0003_custom_ingredients`; существующие строки ингредиентов сохраняются и помечаются как сопоставленные с каталогом.
- Создание и редактирование рецепта принимают либо продукт каталога, либо отдельное исходное название неизвестного ингредиента. Нельзя отправить пустой ингредиент или одновременно передать оба варианта.
- Неизвестный ингредиент сохраняется только в составе конкретного рецепта и не создаёт фиктивную запись в `products`.
- В форме рецепта можно оставить ингредиент локальным либо явно добавить его в общий каталог. Новый продукт создаётся без выдуманных КБЖУ.
- На странице рецепта можно сопоставить локальный ингредиент с существующим продуктом. Сопоставление хранится отдельным `matched_product_id`; исходное имя, количество, единица и примечание не перезаписываются.
- При расчёте КБЖУ сопоставленный ингредиент использует данные выбранного продукта; несопоставленный учитывается как отсутствие данных и переводит расчёт в статус `approximate`.
- Несопоставленные ингредиенты не попадают в корзину. После сопоставления могут добавляться по связи с продуктом каталога.
- При повторном редактировании рецепта связь сопоставления сохраняется.

Проверки:

- `pytest -q`: 29 passed.
- `python -m compileall -q app tests`: успешно.
- Alembic current: `0003_custom_ingredients (head)`.
- SQLite `integrity_check`: `ok`; `foreign_key_check`: нарушений нет.
- Существующие записи не удалены и не переписаны: users 1, recipes 6, recipe_ingredients 18, products 85, product_prices 10, shopping_lists 16, shopping_list_items 30.
- Резервная копия до миграции: `backend/backups/culinary.db.before_custom_ingredients.bak`.
- Сборка frontend не подтверждена: отсутствуют npm-зависимости. Попытка TypeScript-проверки показывает отсутствие React и остальных локальных пакетов; синтаксические ошибки JSX не были выявлены, но это не заменяет полноценную сборку.

Ограничения:

- Массовое сопоставление пользовательских ингредиентов в нескольких рецептах пока не реализовано.
- Автоматическое семантическое сопоставление не выполняется: решение остаётся за владельцем, чтобы не подменять разные продукты.

## Этап 5 — корректность расчёта КБЖУ

**Статус: реализовано, backend-тесты пройдены.**

- Переработан расчёт КБЖУ: отсутствующие значения больше не подменяются нулями в итоговых показателях.
- Для каждого макронутриента итоговое значение возвращается как `null`, если хотя бы для одного ингредиента не хватает исходных данных или нельзя определить массу ингредиента. Отдельные `known_*` поля показывают только известную часть суммы и не выдаются за полный итог.
- Добавлены `missing_components`, `missing_ingredients` и `coverage_percent` для объяснения неполноты расчёта.
- Добавлен расчёт на 100 г исходной массы ингредиентов. Он доступен только когда масса всех ингредиентов известна; потери/впитывание влаги при приготовлении не моделируются.
- Расчёт на порцию пересчитывается по выбранному числу порций, как и ранее.
- Граммы и килограммы приводятся к граммам. Миллилитры/литры и штуки не приравниваются к граммам без плотности или массы одной штуки.
- Данные сопоставленного пользовательского ингредиента продолжают браться из связанного продукта каталога; несопоставленный ингредиент остаётся неизвестным и не получает выдуманных значений.
- Схема БД не менялась; миграция не требуется.

Проверки этапа 5:
- `python -m pytest -q`: 35 passed.
- `python -m compileall -q app tests`: успешно.
- SQLite `integrity_check`: `ok`; `foreign_key_check`: нарушений нет.
- Количество исходных записей сохранено: users 1, recipes 6, recipe_ingredients 18, products 85, product_prices 10, shopping_lists 16, shopping_list_items 30.
- Сборка frontend не подтверждена: `npm run build` запускался, но TypeScript завершился ошибками из-за отсутствующих зависимостей и типов (`react`, `react/jsx-runtime`, `@tanstack/react-query`, `node` и др.); каталог `frontend/node_modules` отсутствует. Полноценную проверку TS/Vite можно выполнить после установки зависимостей.

## Этап 6 — аудит качества каталога продуктов (18.11.2026)

- Добавлен read-only endpoint `GET /api/products/catalog/quality` со сводкой полноты КБЖУ, непроверенных записей, пустых категорий, отсутствующих синонимов и дубликатов.
- В интерфейс каталога добавлена панель качества, список точных дублей-кандидатов и отметка «не проверен» у продукта.
- Уточнён текст поиска: он не зависит от регистра.
- Категория трёх позиций семян (ID 48–50: чиа, кунжут, конопля) исправлена с «Другое» на «Орехи и семена». КБЖУ, идентификаторы и связи не изменялись.
- Данные аудита: 85 продуктов; 73 с полным КБЖУ; 12 с частичным КБЖУ; 0 без КБЖУ; 12 не проверены; 0 без категории; 0 синонимов; одна группа совпадающих названий и один точный кластер-дубликат.
- Дубликаты: ID 31 и 81–85 имеют одинаковое имя, но показатели ID 31 отличаются. ID 81–85 совпадают по категории и КБЖУ. Никакие записи не удалялись и не объединялись из-за возможных ссылок из рецептов.
- Пустые категории: овощи, фрукты и ягоды, мясо, рыба и морепродукты, бобовые, соусы и специи. Не заполнялись вымышленными продуктами.
- Backend: 36 тестов пройдены; compileall успешно; SQLite integrity_check ok; FK check без нарушений.
- Frontend build не пройден: локальные node_modules не содержат React / React typings и ряд прочих зависимостей. Ошибки относятся к разрешению зависимостей/типов, сборка не подтверждена.
- Резервная копия перед этапом: `backend/backups/culinary.db.before_catalog_audit_phase6.bak`.

## Проверка frontend-сборки — 18.11.2026

Проведена повторная попытка восстановления frontend-зависимостей через `npm ci` по `package-lock.json`. Установка заблокирована сетевой ошибкой `EAI_AGAIN` при обращении к `registry.npmjs.org`; после этого `npm run build` подтвердил отсутствие React, React typings, TypeScript/Vite и других npm-пакетов. Ошибки JSX/типизации, возникшие в таком состоянии, не считаются подтверждёнными дефектами исходного кода. Неполный `node_modules` удалён; исходники и lock-файл не менялись. Production-сборка остаётся непроверенной до успешной установки пакетов. Подробности и команды для повторной проверки: `FRONTEND_BUILD_CHECK.md`. До начала работ создана резервная копия БД `backend/backups/culinary.db.before_frontend_dependency_repair_20261118.bak`; рабочая БД не изменялась.

## Этап 7 — единый каталог универсальных продуктов и товаров магазинов

**Статус: backend и начальное наполнение реализованы; полная Vite-сборка ожидает проверки в Windows.**

- Добавлена миграция Alembic `0004_universal_store_products`: нормализованное имя, JSON-характеристики и статус универсального продукта; отдельные таблицы `store_products` и `store_product_prices`.
- Универсальный продукт остаётся единственным типом продукта, на который ссылаются ингредиенты рецептов. Конкретный SKU магазина связан через `universal_product_id`.
- Существующая таблица `product_prices` и старые связи сохранены для обратной совместимости.
- Добавлен идемпотентный seed-каталог по всем 13 категориям. На базе из архива добавлено 948 универсальных продуктов и 115 синонимов; итог — 1 033 продукта. Повторный запуск добавил 0 записей.
- Поиск нормализован по Unicode, регистру, `ё/е`, частичному совпадению; работают фильтрация по категории и пагинация.
- Добавлены API выбора нескольких ID, управления SKU магазинов, истории цен и статусов.
- Переработан импортёр ВкусВилл для создания отдельных SKU и универсальных продуктов. Импорт с внешнего источника не запускался.
- Сервис расчёта стоимости теперь учитывает последние цены SKU в RUB/kg; для объёма и штук не делает неподтверждённых пересчётов.
- Frontend обновлён: пагинация каталога, поиск при сопоставлении ингредиентов, создание магазинного SKU и добавление цены. В рецепте несколько продуктов выбираются несколькими строками ингредиентов; строки можно удалять.
- Существующие 85 продуктов не переименовывались и не мигрировались в SKU автоматически, поскольку для части записей нет достоверных данных бренда/производителя/упаковки и безопасного универсального соответствия. ID, цены и связи сохранены.
- КБЖУ новых 948 позиций оставлено пустым до получения подтверждённых данных; никаких пищевых значений не выдумывалось.
- Резервная копия: `backend/backups/culinary.db.before_phase7_universal_store_catalog.bak`.
- Проверки: 42 backend-теста passed; compileall успешно; миграция проверена на копии базы; SQLite integrity `ok`; foreign keys без нарушений; 33 TS/TSX файла синтаксически корректны; доступный TypeScript 5.8.3 завершил `tsc -b` успешно. Vite build в Linux невозможен из-за отсутствующего Linux native binding Rolldown; требуется повторить `npm run build` на Windows.

Подробности и фактические количества: `PHASE7_REPORT.md`.
