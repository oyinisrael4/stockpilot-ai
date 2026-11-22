"""Validate private free-demo configuration without printing credentials."""
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import json
import os
import sys
import ssl

from dotenv import dotenv_values, set_key

root = Path(__file__).resolve().parents[1]
path = root / 'deploy/.env.render'
config = dotenv_values(path)
if config.get('STOCKPILOT_CLOUD_FREE_ONLY') != '1':
    raise SystemExit('Confirm Groq Free with no billing upgrade, then set STOCKPILOT_CLOUD_FREE_ONLY=1 privately.')
if not config.get('DATABASE_URL') or not config.get('GROQ_API_KEY'):
    raise SystemExit('DATABASE_URL or GROQ_API_KEY is missing from private deploy/.env.render. Do not send credentials in chat.')
try:
    url = urlsplit(config['DATABASE_URL'])
    if (url.scheme not in ('postgres', 'postgresql') or not (url.hostname or '').endswith('.neon.tech')
            or '-pooler' in url.hostname or url.path != '/stockpilot_demo' or url.fragment):
        raise ValueError()
    # Neon commonly supplies sslmode=require; strengthen it before deployment.
    query = parse_qs(url.query)
    query.update(sslmode=['verify-full'], sslrootcert=['system'])
    normalized = urlunsplit((url.scheme, url.netloc, url.path, urlencode(query, doseq=True), ''))
    if normalized != config['DATABASE_URL']:
        set_key(str(path), 'DATABASE_URL', normalized)
        config['DATABASE_URL'] = normalized
except (ValueError, TypeError):
    raise SystemExit('Use the direct Neon URL for stockpilot_demo, without -pooler. Nothing was connected.') from None

try:
    import psycopg
    tls = {}
    if os.name == 'nt':
        # libpq's OpenSSL does not read the Windows native trust store itself.
        # Export public CA certificates, keeping full hostname verification enabled.
        ca_file = root / '.local/cloud-ca.pem'
        ca_file.parent.mkdir(exist_ok=True)
        ca_file.write_text(''.join(ssl.DER_cert_to_PEM_cert(c) for c in ssl.create_default_context().get_ca_certs(binary_form=True)), encoding='ascii')
        tls['sslrootcert'] = str(ca_file)
    with psycopg.connect(config['DATABASE_URL'], connect_timeout=20, **tls) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT current_database()')
            if cursor.fetchone()[0] != 'stockpilot_demo': raise ValueError()
    print('Neon: authenticated, TLS certificate verification enabled, isolated database confirmed. No records changed.')
except Exception as error:
    raise SystemExit('Neon verification failed (' + type(error).__name__ + '). Check the private URL/network; no credentials were printed.') from None

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs): return None

try:
    request = Request('https://api.groq.com/openai/v1/models', headers={'Authorization': 'Bearer ' + config['GROQ_API_KEY'],
                      'User-Agent': 'StockPilotAI/1.0', 'Accept': 'application/json'})
    with build_opener(NoRedirect()).open(request, timeout=25) as response:
        raw = response.read(262145)
    if len(raw) > 262144: raise ValueError()
    available = {row['id'] for row in json.loads(raw)['data']}
    if not {config.get('STOCKPILOT_AI_MODEL', 'openai/gpt-oss-120b'), config.get('STOCKPILOT_GROQ_VOICE_MODEL', 'whisper-large-v3-turbo')} <= available: raise ValueError()
    print('Groq: API key accepted; selected chat and speech model IDs are listed. No inference request was sent.')
except Exception as error:
    raise SystemExit('Groq availability check failed (' + type(error).__name__ + '). Check the Free account/model permissions privately.') from None
print('Provider setup checks passed. Free billing status still requires confirmation in your provider dashboards.')
