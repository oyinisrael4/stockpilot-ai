"""Create a private cloud environment file without changing local app settings."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
target = root / 'deploy/.env.render'
if target.exists(): raise SystemExit('Private deploy/.env.render already exists; left untouched.')
template = (root / 'deploy/render.env.example').read_text(encoding='utf-8')
for key in ('DJANGO_SECRET_KEY', 'STOCKPILOT_DEMO_PASSWORD', 'STOCKPILOT_DEMO_VISITOR_PASSWORD'):
    template = template.replace(key + '=\n', key + '=' + secrets.token_urlsafe(48) + '\n')
template = template.replace('STOCKPILOT_CLOUD_FREE_ONLY=1', 'STOCKPILOT_CLOUD_FREE_ONLY=0')
target.write_text(template, encoding='utf-8')
print('Created private deploy/.env.render. Add DATABASE_URL and GROQ_API_KEY locally; confirm the Free plan before changing CLOUD_FREE_ONLY to 1. No credentials were printed.')
