"""Live Groq + Neon verification using Django's in-process HTTPS test client.

Only runs against the explicitly configured fictional database. It records one
fictional sale and retains its audit trail; never deletes or resets workspaces.
"""
import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4
from decimal import Decimal
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
config = dotenv_values(root / 'deploy/.env.render')
if config.get('STOCKPILOT_CLOUD_FREE_ONLY') != '1' or not config.get('GROQ_API_KEY') or not config.get('DATABASE_URL'):
    raise SystemExit('Complete the private Free-plan configuration and preflight first.')
for key, value in config.items():
    if value is not None: os.environ[key] = value
os.environ.update(DJANGO_DEBUG='0', DJANGO_ALLOWED_HOSTS='testserver', DJANGO_TRUSTED_ORIGINS='https://testserver',
                  STOCKPILOT_PUBLIC_URL='https://testserver', STOCKPILOT_DEMO_COOKIE_ISOLATION='0')
if os.name == 'nt': os.environ['PGSSLROOTCERT'] = str(root / '.local/cloud-ca.pem')
sys.path.insert(0, str(root / 'backend'))
os.environ['DJANGO_SETTINGS_MODULE'] = 'stockpilot.settings'
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient
from core.models import Business, User, Product, Sale, StockMovement
from core.assistant_tools import local_day

if connection.settings_dict['NAME'] != 'stockpilot_demo' or not connection.settings_dict['HOST'].endswith('.neon.tech'):
    raise SystemExit('Live verification only permits the dedicated Neon stockpilot_demo database.')
if settings.ASSISTANT_PROVIDER != 'groq' or settings.VOICE_PROVIDER != 'groq':
    raise SystemExit('Both cloud providers must be Groq for live verification.')
call_command('migrate', interactive=False, verbosity=0)
call_command('createcachetable', verbosity=0)
print('Neon schema and shared cache initialized.', flush=True)
if not Business.objects.exists() and not User.objects.exists():
    print('Seeding the empty fictional workspace; existing records will never be replaced.', flush=True)
    call_command('seed_portfolio_demo', hosted=True)
business = Business.objects.get(name='Juniper Market Supply · Demo')
client = APIClient(enforce_csrf_checks=True)
assert client.get('/api/v1/auth/session/', secure=True).status_code == 200
headers = {'HTTP_X_CSRFTOKEN': client.cookies[settings.CSRF_COOKIE_NAME].value, 'HTTP_ORIGIN': 'https://testserver'}
assert client.post('/api/v1/auth/demo/', secure=True, **headers).status_code == 200
headers['HTTP_X_CSRFTOKEN'] = client.cookies[settings.CSRF_COOKIE_NAME].value
base = f'/api/v1/businesses/{business.pk}/assistant/'
thread = client.post(base + 'conversations/', secure=True, **headers).data['id']
last_request = 0

def message(text):
    global last_request
    # Also leave capacity for requests made just before this verification script.
    remaining = 31 - (time.monotonic() - last_request)
    if remaining > 0: time.sleep(remaining)
    last_request = time.monotonic()
    response = client.post(base + f'conversations/{thread}/messages/',
                           {'text': text, 'request_id': str(uuid4())}, format='json', secure=True, **headers)
    if response.status_code != 201 or response.data.get('answer', {}).get('mode') != 'provider':
        raise RuntimeError('Live cloud message did not produce a validated provider result. Inspect the app quota/model configuration privately.')
    return response.data

product = Product.objects.get(business=business, sku='WATER-75')
before_stock, before_sales = product.stock, Sale.objects.filter(business=business).count()
if before_stock < 2: raise SystemExit('Insufficient fictional stock for verification; no adjustment was made.')
proposal = message('Please sell two bottles of WATER-75, paid in cash.')['proposal']
assert proposal and proposal['status'] == 'pending'
assert Sale.objects.filter(business=business).count() == before_sales
url = base + f"proposals/{proposal['id']}/confirm/"
data = {'revision': proposal['revision']}
first = client.post(url, data, format='json', secure=True, **headers)
again = client.post(url, data, format='json', secure=True, **headers)
assert first.status_code == again.status_code == 200
assert first.data['proposal']['result'] == again.data['proposal']['result']
product.refresh_from_db()
assert product.stock == before_stock - Decimal(2)
assert Sale.objects.filter(business=business).count() == before_sales + 1
print('Real Groq sale intent, explicit confirmation, duplicate retry and persisted Neon stock passed.', flush=True)
answer = message('How much gross profit did we make this month?')
assert not answer['proposal'] and answer['answer'].get('card')
followup = message('What about last month?')
assert not followup['proposal'] and followup['answer'].get('card')
print('Real cloud multi-turn database-backed report follow-up passed.', flush=True)
audio = (root / '.local/voice-verification.wav').read_bytes()
sales_before_audio = Sale.objects.filter(business=business).count()
transcription = client.post(base + 'transcribe/', audio, content_type='audio/wav', secure=True, **headers)
assert transcription.status_code == 200 and 'water' in transcription.data['text'].lower()
assert Sale.objects.filter(business=business).count() == sales_before_audio
print('Real Groq Whisper transcription passed without recording a financial transaction.', flush=True)
pending = message('Please prepare a cash sale of one WATER-75.')['proposal']
assert pending and pending['status'] == 'pending'
before_cancel = Product.objects.get(pk=product.pk).stock
cancel = client.post(base + f"proposals/{pending['id']}/cancel/", {'revision': pending['revision']}, format='json', secure=True, **headers)
assert cancel.status_code == 200
assert Product.objects.get(pk=product.pk).stock == before_cancel
assert Sale.objects.filter(business=business).count() == before_sales + 1
print('Live proposal cancellation left sales and inventory unchanged.', flush=True)
report = {'verified_at': timezone.now().isoformat(), 'chat_provider': 'groq', 'model': settings.ASSISTANT_MODEL,
          'speech_model': settings.GROQ_VOICE_MODEL, 'database': 'isolated Neon stockpilot_demo',
          'results': ['cloud intent', 'confirmed sale', 'duplicate confirmation', 'Neon persistence', 'multi-turn reports',
                      'actual cloud transcription', 'cancel without writes'],
          'limitation': 'In-process production-settings HTTPS client; public Render ingress/browser still requires separate verification.'}
(root / '.local/cloud-live-verification.json').write_text(json.dumps(report, indent=2))
print('Live cloud integration verification complete. One fictional sale and its audit trail were retained.', flush=True)
