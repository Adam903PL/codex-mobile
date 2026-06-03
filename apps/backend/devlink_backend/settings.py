from datetime import timedelta
from pathlib import Path
import os
import sys

BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)


def load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "devlink-dev-secret-key-change-me-for-local-development")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"


def csv_env(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


ALLOWED_HOSTS = csv_env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
if DEBUG and "DJANGO_ALLOWED_HOSTS" not in os.environ:
    ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "channels",
    "django_filters",
    "drf_spectacular",
    "accounts.apps.AccountsConfig",
    "devices.apps.DevicesConfig",
    "projects.apps.ProjectsConfig",
    "sessions.apps.SessionsConfig",
    "tasks.apps.TasksConfig",
    "agents.apps.AgentsConfig",
    "terminals.apps.TerminalsConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "devlink_backend.dev_logs.ApiJsonExceptionMiddleware",
    "devlink_backend.dev_logs.RecentRequestLogMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "devlink_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "devlink_backend.wsgi.application"
ASGI_APPLICATION = "devlink_backend.asgi.application"

DB_ENGINE = os.getenv("DB_ENGINE", "django.db.backends.sqlite3")

if DB_ENGINE == "django.db.backends.postgresql":
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": os.getenv("DB_NAME", "devlink"),
            "USER": os.getenv("DB_USER", "devlink"),
            "PASSWORD": os.getenv("DB_PASSWORD", "devlink_password"),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "54329"),
            "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "0")),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": DB_ENGINE,
            "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "pl-pl"
TIME_ZONE = "Europe/Warsaw"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CORS_ALLOWED_ORIGINS = csv_env("CORS_ALLOWED_ORIGINS", "http://localhost:8081")
CORS_ALLOW_ALL_ORIGINS = DEBUG and "CORS_ALLOWED_ORIGINS" not in os.environ

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "devlink_backend.exceptions.devlink_exception_handler",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "DevLink API",
    "DESCRIPTION": "REST API dla aplikacji mobilnej i lokalnego CLI DevLink.",
    "VERSION": "0.1.0",
}

DEFAULT_CHANNEL_LAYER_BACKEND = (
    "channels.layers.InMemoryChannelLayer"
    if DEBUG or "test" in sys.argv
    else "channels_redis.core.RedisChannelLayer"
)

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": os.getenv("CHANNEL_LAYER_BACKEND", DEFAULT_CHANNEL_LAYER_BACKEND),
        "CONFIG": {
            "hosts": [os.getenv("CHANNEL_REDIS_URL", "redis://127.0.0.1:63799/0")],
        },
    }
}

if CHANNEL_LAYERS["default"]["BACKEND"] == "channels.layers.InMemoryChannelLayer":
    CHANNEL_LAYERS["default"].pop("CONFIG", None)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "devlink": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "devlink",
        },
        "devlink_file": {
            "class": "logging.FileHandler",
            "filename": str(LOG_DIR / "devlink.log"),
            "formatter": "devlink",
            "encoding": "utf-8",
        },
    },
    "root": {
        "handlers": ["console", "devlink_file"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {
            "handlers": ["console", "devlink_file"],
            "level": "WARNING",
            "propagate": False,
        },
        "devlink_backend": {
            "handlers": ["console", "devlink_file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
