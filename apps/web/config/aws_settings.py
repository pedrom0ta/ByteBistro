import os

from django.core.exceptions import ImproperlyConfigured

from .settings import *


def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"Configure {name} for the AWS deployment.")
    return value


DEBUG = False
SECRET_KEY = required_env("DJANGO_SECRET_KEY")
PUBLIC_HOST = required_env("BYTEBISTRO_PUBLIC_HOST")
ORIGIN_HOST = required_env("BYTEBISTRO_ORIGIN_HOST")
ALLOWED_HOSTS = [PUBLIC_HOST, ORIGIN_HOST]
CSRF_TRUSTED_ORIGINS = [f"https://{PUBLIC_HOST}"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_BYTEBISTRO_VIEWER_PROTO", "https")
SECURE_SSL_REDIRECT = True
SECURE_SSL_HOST = PUBLIC_HOST
MIDDLEWARE = ["config.aws_health.readiness_middleware", *MIDDLEWARE]
STATIC_ROOT = Path("/app/collected-static")
BYTEBISTRO_GRAPHQL_URL = os.environ.get("BYTEBISTRO_GRAPHQL_URL")
GRAPHQL_SERVICE_TOKEN = required_env("GRAPHQL_SERVICE_TOKEN") if BYTEBISTRO_GRAPHQL_URL else ""
BYTEBISTRO_OUTBOX_ENABLED = os.environ.get("BYTEBISTRO_OUTBOX_ENABLED", "0") == "1"
SMS_PROVIDER = os.environ.get("SMS_PROVIDER") or "shop.sms.SnsSmsProvider"
SMS_COUNTRY_CODE = os.environ.get("SMS_COUNTRY_CODE") or "+55"
CACHES = {
    "default": {
        "BACKEND": "config.aws_cache.PostgresCache",
        "LOCATION": "bytebistro_cache",
    },
}

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": required_env("PGHOST"),
        "PORT": os.environ.get("PGPORT", "5432"),
        "NAME": required_env("PGDATABASE"),
        "USER": required_env("PGUSER"),
        "PASSWORD": required_env("PGPASSWORD"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "sslmode": "verify-full",
            "sslrootcert": os.environ.get("PGSSLROOTCERT", "/app/rds-ca.pem"),
            "connect_timeout": 3,
        },
    }
}
