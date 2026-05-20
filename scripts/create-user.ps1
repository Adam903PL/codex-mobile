$ErrorActionPreference = "Stop"

Set-Location "$PSScriptRoot\..\apps\backend"

$Username = if ($env:DEVLINK_USERNAME) { $env:DEVLINK_USERNAME } else { "devlink" }
$Password = if ($env:DEVLINK_PASSWORD) { $env:DEVLINK_PASSWORD } else { "devlinkpass123" }
$Email = if ($env:DEVLINK_EMAIL) { $env:DEVLINK_EMAIL } else { "devlink@example.local" }

$env:DB_ENGINE = "django.db.backends.postgresql"
$env:DB_NAME = "devlink"
$env:DB_USER = "devlink"
$env:DB_PASSWORD = "devlink_password"
$env:DB_HOST = "127.0.0.1"
$env:DB_PORT = "54329"
$env:DB_CONN_MAX_AGE = "0"

if (!(Test-Path ".venv\Scripts\python.exe")) {
  throw "Backend venv not found. Run .\scripts\dev-backend.ps1 first."
}

$code = @"
import os
import sys
import django
from django.contrib.auth import get_user_model

username = "$Username"
password = "$Password"
email = "$Email"

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "devlink_backend.settings")
sys.path.insert(0, os.getcwd())
django.setup()

User = get_user_model()
user, created = User.objects.get_or_create(
    username=username,
    defaults={"email": email, "is_active": True},
)
user.email = email
user.is_active = True
user.set_password(password)
user.save()

print(("created" if created else "updated") + f" user {username}")
"@

$tmp = New-TemporaryFile
try {
  Set-Content -LiteralPath $tmp -Value $code -Encoding UTF8
  .\.venv\Scripts\python.exe $tmp
  if ($LASTEXITCODE -ne 0) {
    throw "User creation failed with exit code $LASTEXITCODE."
  }
} finally {
  Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
}
Write-Host "Login: $Username"
Write-Host "Password: $Password"
