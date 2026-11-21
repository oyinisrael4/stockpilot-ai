"""Run behind a TLS reverse proxy on the same host. Never use Vite/runserver publicly."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockpilot.settings")
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from stockpilot.wsgi import application
from waitress import serve

if settings.DEBUG:
    raise ImproperlyConfigured("Production startup requires DJANGO_DEBUG=0.")
serve(application, host="127.0.0.1", port=int(os.getenv("STOCKPILOT_PORT", "8000")),
      threads=4, connection_limit=64, channel_timeout=150, max_request_body_size=2 * 1024 * 1024,
      trusted_proxy="127.0.0.1", trusted_proxy_count=1,
      trusted_proxy_headers={"x-forwarded-proto", "x-forwarded-for"}, clear_untrusted_proxy_headers=True)
