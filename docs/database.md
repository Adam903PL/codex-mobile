# Lokalna baza danych

DevLink używa lokalnego PostgreSQL uruchamianego przez Docker Compose.

## Start

```bash
docker compose up -d postgres
```

Kontener:

```text
name: devlink-postgres
image: postgres:17-alpine
host: 127.0.0.1
port: 54329
database: devlink
user: devlink
password: devlink_password
```

Backend czyta ustawienia z `apps/backend/.env`. Plik jest lokalny i ignorowany przez Git.

## Migracje

```bash
cd apps/backend
python manage.py migrate
```

## Sprawdzenie bazy używanej przez Django

```bash
cd apps/backend
python manage.py shell -c "from django.db import connection; print(connection.vendor, connection.settings_dict['NAME'])"
```

Oczekiwany wynik:

```text
postgresql devlink
```

## Stop

```bash
docker compose stop postgres
```

## Reset danych

To usuwa lokalne dane bazy.

```bash
docker compose down -v
docker compose up -d postgres
cd apps/backend
python manage.py migrate
```

