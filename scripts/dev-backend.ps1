$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."
docker compose up -d postgres redis
Set-Location "$PSScriptRoot\..\apps\backend"
$env:DB_ENGINE = "django.db.backends.postgresql"
$env:DB_NAME = "devlink"
$env:DB_USER = "devlink"
$env:DB_PASSWORD = "devlink_password"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "54329"
$env:DB_CONN_MAX_AGE = "0"
$env:CHANNEL_REDIS_URL = "redis://127.0.0.1:63799/0"
$env:DJANGO_ALLOWED_HOSTS = "*"
if (!(Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}
if (!(Test-Path ".venv")) {
  py -m venv .venv
}
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py runserver 0.0.0.0:8000
