"""
logmonitor/settings/production.py
─────────────────────────────────────────────────────────────────
Paramètres de PRODUCTION.
Toutes les variables sensibles sont lues depuis l'environnement.
Ne jamais committer ce fichier avec des valeurs réelles.
"""

from .base import *  # noqa
import environ

env = environ.Env()

# ── Sécurité absolue ──────────────────────────────────────────────────────────
DEBUG = False
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Headers HTTPS stricts
SECURE_SSL_REDIRECT           = True
SECURE_HSTS_SECONDS           = 31536000  # 1 an
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD           = True
SESSION_COOKIE_SECURE         = True
CSRF_COOKIE_SECURE            = True

# ── Base de données ───────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        **env.db("DATABASE_URL"),
        "CONN_MAX_AGE": 60,           # Connexions persistantes
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c default_transaction_isolation=read committed",
        },
    }
}

# ── Cache (Redis recommandé en production) ────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://127.0.0.1:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND    = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST       = env("EMAIL_HOST", default="smtp.sendgrid.net")
EMAIL_PORT       = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS    = True
EMAIL_HOST_USER  = env("EMAIL_HOST_USER", default="apikey")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL  = env("DEFAULT_FROM_EMAIL", default="noreply@logmonitor.io")

# ── Logging de production ─────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "file_error": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": "/var/log/logmonitor/error.log",
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "level": "ERROR",
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django.security": {
            "handlers": ["file_error"],
            "level": "ERROR",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ── Clés API (configurer via env) ─────────────────────────────────────────────
API_KEYS = env.list("API_KEYS", default=[])

# ── Sentry (optionnel) ───────────────────────────────────────────────────────
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
