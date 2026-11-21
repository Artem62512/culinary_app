# Безопасный запуск

1. Скопируйте `.env.example` в `.env`.
2. Задайте уникальные `APP_USERNAME` и `APP_PASSWORD` (не используйте пример).
3. Запускайте приложение только за HTTPS reverse proxy, поскольку используется HTTP Basic.
4. Не публикуйте SQLite-файл, `.env`, резервные копии и `/docs`.
5. Если пароль не задан, API закрывает доступ с HTTP 503, а не открывает его анонимно.

Эта реализация предназначена для одного владельца/небольшого приватного развёртывания. Для публичного многопользовательского сервиса следует перейти на персональные аккаунты, хеширование паролей и JWT/session cookies с CSRF-защитой.

## Database migrations

Run migrations from the `backend` directory after creating a verified backup:

```powershell
python -m alembic upgrade head
```

The initial migration assigns existing recipes with a missing `user_id` to the
sole owner account. It requires exactly one row in `users`; if that condition is
not met, it stops without changing recipe ownership. Recipe IDs, ingredients,
and recipe content are preserved.

For a new empty installation, initialize the application schema and sole owner
using the documented startup/bootstrap process before running the migration.


Migration `0003_custom_ingredients` allows recipe ingredients to be stored without
a catalog product. Such rows retain the original name, quantity, unit, and note.
An explicit match to a catalog product is stored separately and does not overwrite
the original ingredient name or amount. Unmatched custom ingredients are excluded
from shopping-cart generation until they are matched.
