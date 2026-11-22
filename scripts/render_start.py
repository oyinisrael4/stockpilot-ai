"""Render-only cloud startup. Does not expose local Windows services."""
import os
from pathlib import Path
import sys

if os.getenv("RENDER") != "true":
    raise SystemExit("This startup command is for Render containers only. Use the local startup scripts on your computer.")
host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if not host or not host.endswith(".onrender.com"):
    raise SystemExit("Render's external HTTPS hostname is required.")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", host)
os.environ.setdefault("DJANGO_TRUSTED_ORIGINS", "https://" + host)
os.environ.setdefault("STOCKPILOT_PUBLIC_URL", "https://" + host)
os.environ["DJANGO_TRUST_HTTPS_PROXY"] = "1"
os.environ["STOCKPILOT_DEMO_COOKIE_ISOLATION"] = "0"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockpilot.settings")

import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from core.models import Business, User

if settings.DEBUG or settings.ASSISTANT_PROVIDER != "groq" or settings.VOICE_PROVIDER != "groq":
    raise SystemExit("The free hosted demo requires production settings and the configured cloud providers.")
if connection.settings_dict["NAME"] != "stockpilot_demo" or os.getenv("STOCKPILOT_PUBLIC_DEMO") != "1":
    raise SystemExit("Hosted demo startup requires the isolated stockpilot_demo database.")
if not os.environ.get("DATABASE_URL"):
    raise SystemExit("Set the private direct Neon DATABASE_URL in Render's environment settings.")
call_command("migrate", interactive=False, verbosity=0)
call_command("createcachetable", verbosity=0)
if os.getenv("STOCKPILOT_SEED_HOSTED_DEMO") == "1" and not Business.objects.exists() and not User.objects.exists():
    call_command("seed_portfolio_demo", hosted=True)

from stockpilot.wsgi import application
from waitress import serve
# Render's ingress is the only public path to this container. It supplies the last
# forwarded hop; never reuse this trust configuration on an unprotected host.
serve(application, host="0.0.0.0", port=int(os.getenv("PORT", "10000")), threads=4,
      connection_limit=32, channel_timeout=90, max_request_body_size=2 * 1024 * 1024,
      trusted_proxy="*", trusted_proxy_count=1,
      trusted_proxy_headers={"x-forwarded-proto", "x-forwarded-for"}, clear_untrusted_proxy_headers=True)
