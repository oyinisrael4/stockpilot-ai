import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DEBUG = os.getenv("DJANGO_DEBUG") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY in the environment or .env")
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
CSRF_TRUSTED_ORIGINS = [origin for origin in os.getenv("DJANGO_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173" if DEBUG else "").split(",") if origin]
ROOT_URLCONF = "stockpilot.urls"
WSGI_APPLICATION = "stockpilot.wsgi.application"
INSTALLED_APPS = [
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "rest_framework", "drf_spectacular", "core",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.ApiPrivacyMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": os.getenv("PGDATABASE", "stockpilot"),
    "USER": os.getenv("PGUSER", "stockpilot"),
    "PASSWORD": os.getenv("PGPASSWORD", ""),
    "HOST": os.getenv("PGHOST", "127.0.0.1"),
    "PORT": os.getenv("PGPORT", "55432"),
    "CONN_MAX_AGE": 60 if not DEBUG else 0,
    "CONN_HEALTH_CHECKS": True,
    "OPTIONS": {"connect_timeout": 5, "options": "-c statement_timeout=30000 -c lock_timeout=10000",
                **({"sslmode": os.environ["PGSSLMODE"]} if os.getenv("PGSSLMODE") else {})},
}}
if os.getenv("DATABASE_URL"):
    parsed = urlsplit(os.environ["DATABASE_URL"])
    if parsed.scheme not in ("postgres", "postgresql") or not parsed.hostname or "-pooler" in parsed.hostname:
        raise ImproperlyConfigured("Use a direct PostgreSQL DATABASE_URL, not a transaction-pooler endpoint.")
    sslmode = parse_qs(parsed.query).get("sslmode", ["verify-full"])[0]
    if not DEBUG and sslmode != "verify-full":
        raise ImproperlyConfigured("Production DATABASE_URL requires sslmode=verify-full.")
    DATABASES["default"].update(NAME=unquote(parsed.path.lstrip("/")), USER=unquote(parsed.username or ""),
                                PASSWORD=unquote(parsed.password or ""), HOST=parsed.hostname, PORT=str(parsed.port or 5432),
                                CONN_MAX_AGE=0,
                                OPTIONS={"connect_timeout": 15, "sslmode": sslmode,
                                         **({"sslrootcert": os.getenv("PGSSLROOTCERT", "system")} if sslmode == "verify-full" else {}),
                                         "options": "-c statement_timeout=30000 -c lock_timeout=10000"})
AUTH_USER_MODEL = "core.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{validator}"}
    for validator in ("UserAttributeSimilarityValidator", "MinimumLengthValidator",
                      "CommonPasswordValidator", "NumericPasswordValidator")
]
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# Browsers share cookies across ports on the same host. Keep demo sign-in separate.
if DATABASES["default"]["NAME"] == "stockpilot_demo" and os.getenv("STOCKPILOT_DEMO_COOKIE_ISOLATION", "1") == "1":
    SESSION_COOKIE_NAME = "stockpilot_demo_sessionid"
    CSRF_COOKIE_NAME = "stockpilot_demo_csrftoken"
SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = CSRF_COOKIE_SAMESITE = "Lax"
PASSWORD_RESET_TIMEOUT = 3600
ALLOW_REGISTRATION = os.getenv("STOCKPILOT_ALLOW_REGISTRATION", "1" if DEBUG else "0") == "1"
PASSWORD_RESET_ENABLED = os.getenv("STOCKPILOT_PASSWORD_RESET_ENABLED", "1") == "1"
DATA_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 250
SESSION_COOKIE_AGE = 60 * 60 * 12
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("DJANGO_HSTS_INCLUDE_SUBDOMAINS") == "1"
SECURE_HSTS_PRELOAD = os.getenv("DJANGO_HSTS_PRELOAD") == "1"
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
if os.getenv("DJANGO_TRUST_HTTPS_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_REFERRER_POLICY = "same-origin"
EMAIL_BACKEND = os.getenv("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("DJANGO_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("DJANGO_EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("DJANGO_EMAIL_TLS", "1") == "1"
EMAIL_HOST_USER = os.getenv("DJANGO_EMAIL_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("DJANGO_EMAIL_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DJANGO_FROM_EMAIL", "stockpilot@localhost")
PUBLIC_URL = os.getenv("STOCKPILOT_PUBLIC_URL", "http://localhost:5173" if DEBUG else "")
if not PUBLIC_URL or (not DEBUG and not PUBLIC_URL.startswith("https://")):
    raise ImproperlyConfigured("Set STOCKPILOT_PUBLIC_URL to the public HTTPS origin")
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "NUM_PROXIES": 0,  # Trusted WSGI proxy handling sets REMOTE_ADDR; ignore arbitrary forwarded-for headers.
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_RATES": {"account": "12/minute", "assistant_messages": "25/minute", "business_reports": "60/minute"},
}
ASSISTANT_API_KEY = os.getenv("STOCKPILOT_AI_API_KEY", "")
ASSISTANT_MODEL = os.getenv("STOCKPILOT_AI_MODEL", "")
ASSISTANT_PROVIDER = os.getenv("STOCKPILOT_AI_PROVIDER", "openai")
if ASSISTANT_PROVIDER not in ("openai", "ollama", "groq"):
    raise ImproperlyConfigured("STOCKPILOT_AI_PROVIDER must be openai, ollama or groq")
ASSISTANT_ENDPOINT = os.getenv("STOCKPILOT_AI_ENDPOINT", "https://api.openai.com/v1/chat/completions")
ASSISTANT_OLLAMA_ENDPOINT = os.getenv("STOCKPILOT_OLLAMA_ENDPOINT", "http://127.0.0.1:11434/api/chat")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
VOICE_PROVIDER = os.getenv("STOCKPILOT_VOICE_PROVIDER", "offline")
GROQ_VOICE_MODEL = os.getenv("STOCKPILOT_GROQ_VOICE_MODEL", "whisper-large-v3-turbo")
if VOICE_PROVIDER not in ("offline", "groq"):
    raise ImproperlyConfigured("STOCKPILOT_VOICE_PROVIDER must be offline or groq")
# Deliberately conservative, shared application budgets; provider limits still apply.
CLOUD_CHAT_DAILY_LIMIT = int(os.getenv("STOCKPILOT_CLOUD_CHAT_DAILY_LIMIT", "50"))
CLOUD_CHAT_MINUTE_LIMIT = int(os.getenv("STOCKPILOT_CLOUD_CHAT_MINUTE_LIMIT", "2"))
CLOUD_AUDIO_DAILY_SECONDS = int(os.getenv("STOCKPILOT_CLOUD_AUDIO_DAILY_SECONDS", "600"))
CLOUD_AUDIO_HOURLY_SECONDS = int(os.getenv("STOCKPILOT_CLOUD_AUDIO_HOURLY_SECONDS", "120"))
if not (1 <= CLOUD_CHAT_DAILY_LIMIT <= 500 and 1 <= CLOUD_CHAT_MINUTE_LIMIT <= 5
        and 1 <= CLOUD_AUDIO_DAILY_SECONDS <= 3600 and 1 <= CLOUD_AUDIO_HOURLY_SECONDS <= 600):
    raise ImproperlyConfigured("Cloud inference budgets exceed this free-demo configuration's allowed bounds.")
SERVE_FRONTEND = os.getenv("STOCKPILOT_SERVE_FRONTEND") == "1"
FRONTEND_DIST = ROOT / "frontend" / "dist"
SPECTACULAR_SETTINGS = {
    "TITLE": "StockPilot AI API",
    "VERSION": "0.3.0",
    "ENUM_NAME_OVERRIDES": {"TenderMethod": "core.models.Tender"},
}

# Database cache shares throttles between WSGI workers. Run createcachetable before production startup.
CACHES = {"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache" if DEBUG else "django.core.cache.backends.db.DatabaseCache",
    "LOCATION": "stockpilot-local" if DEBUG else "stockpilot_cache",
}}
if not DEBUG:
    if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5:
        raise ImproperlyConfigured("Use a randomly generated production secret of at least 50 characters.")
    if "*" in ALLOWED_HOSTS or not os.getenv("DJANGO_ALLOWED_HOSTS"):
        raise ImproperlyConfigured("Set explicit DJANGO_ALLOWED_HOSTS for production.")
    if any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS):
        raise ImproperlyConfigured("Production trusted origins must use HTTPS.")
    if EMAIL_BACKEND.endswith("console.EmailBackend"):
        raise ImproperlyConfigured("Console email is disabled in production.")
    if os.getenv("STOCKPILOT_PUBLIC_DEMO") == "1" and DATABASES["default"]["NAME"] != "stockpilot_demo":
        raise ImproperlyConfigured("Public demo mode requires the dedicated stockpilot_demo database.")
    if ASSISTANT_PROVIDER == "groq" or VOICE_PROVIDER == "groq":
        if not GROQ_API_KEY or os.getenv("STOCKPILOT_CLOUD_FREE_ONLY") != "1":
            raise ImproperlyConfigured("Cloud deployment requires a private Groq key and explicit Free-plan confirmation.")
    if ASSISTANT_PROVIDER == "groq" and ASSISTANT_MODEL not in ("openai/gpt-oss-20b", "openai/gpt-oss-120b"):
        raise ImproperlyConfigured("Select a supported Groq strict-output model.")

if not DEBUG:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "filters": {"safe_errors": {"()": "core.logging.SafeErrorFilter"}},
        "formatters": {"brief": {"format": "%(levelname)s %(name)s %(message)s"}},
        "handlers": {"safe_console": {"class": "logging.StreamHandler", "filters": ["safe_errors"], "formatter": "brief"}},
        "loggers": {
            "django.request": {"handlers": ["safe_console"], "level": "WARNING", "propagate": False},
            "django.security": {"handlers": ["safe_console"], "level": "WARNING", "propagate": False},
        },
    }
