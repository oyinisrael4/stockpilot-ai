"""Read-only publication gate. Never prints credentials or file contents."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
config = dotenv_values(ROOT / '.env')
secrets = [v.encode() for k, v in config.items() if v and len(v) >= 8
           and any(word in k for word in ('SECRET', 'PASSWORD', 'API_KEY'))]
password = ROOT / '.local/portfolio-demo-password'
if password.exists():
    secrets.append(password.read_bytes().strip())
patterns = [rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
            rb'gh[pousr]_[A-Za-z0-9]{30,}', rb'github_pat_[A-Za-z0-9_]{50,}',
            rb'AKIA[A-Z0-9]{16}', rb'sk-(?:proj-)?[A-Za-z0-9_-]{35,}']
findings = []

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)

def forbidden(name):
    path = Path(name)
    parts = set(path.parts)
    return (bool(parts & {'.local', '.venv', 'node_modules', '__pycache__', 'dist', 'dist-showcase'})
            or (path.name.startswith('.env') and path.name != '.env.example')
            or path.suffix.lower() in {'.gguf', '.safetensors', '.onnx', '.pt', '.pth', '.bin', '.dump', '.backup', '.sqlite3', '.db', '.wav', '.mp3', '.webm', '.log'}
            or name.endswith('.manifest.json'))

def scan(label, content):
    if any(value and value in content for value in secrets) or any(re.search(p, content) for p in patterns):
        findings.append('Possible credential in ' + label)

paths = git('ls-files', '--cached', '--others', '--exclude-standard', '-z').decode().split('\0')
paths = sorted(set(p for p in paths if p))
for name in paths:
    if forbidden(name): findings.append('Excluded artifact is git-visible: ' + name)
    if (ROOT / name).is_file(): scan(name, (ROOT / name).read_bytes())

# Inspect every reachable blob, including content deleted in a later commit.
objects = git('rev-list', '--objects', '--all').decode().splitlines()
history_blobs = 0
if objects:
    # One process avoids hundreds of slow Git launches on Windows.
    batch = subprocess.Popen(['git', 'cat-file', '--batch'], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    batch.stdin.write(('\n'.join(line.partition(' ')[0] for line in objects) + '\n').encode())
    batch.stdin.close()
    for line in objects:
        oid, _, name = line.partition(' ')
        _, kind, size = batch.stdout.readline().split()
        content = batch.stdout.read(int(size))
        batch.stdout.read(1)
        if kind == b'blob':
            history_blobs += 1
            if forbidden(name): findings.append('Excluded artifact in history: ' + name)
            scan('history blob ' + oid[:12], content)
    if batch.wait(): raise SystemExit('Git history audit failed.')

dist = ROOT / 'frontend/dist-showcase'
if not (dist / 'index.html').is_file(): raise SystemExit('Build the showcase before auditing.')
artifacts = []
for path in sorted(dist.rglob('*')):
    if not path.is_file(): continue
    name = path.relative_to(dist).as_posix()
    if not (name == 'index.html' or name == '_headers' or name.startswith('assets/') or name.startswith('portfolio/')):
        findings.append('Unexpected deployment artifact: ' + name)
    if path.suffix not in {'.html', '.css', '.js', '.webp', '.png'} and name != '_headers':
        findings.append('Unexpected deployment file type: ' + name)
    content = path.read_bytes()
    scan('deployment/' + name, content)
    artifacts.append({'path': name, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest()})

report = {'git_visible_files': len(paths), 'commits': int(git('rev-list', '--all', '--count')),
          'historical_blobs': history_blobs, 'deployment_files': artifacts,
          'deployment_bytes': sum(f['bytes'] for f in artifacts), 'findings': findings,
          'limitations': 'Pattern/exact-secret audit is not a guarantee; manually review public media and new secrets before publishing.'}
out = ROOT / '.local/phase8-publication-audit.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(report, indent=2))
print(json.dumps({k: v for k, v in report.items() if k != 'deployment_files'}, indent=2))
if findings: raise SystemExit(1)
