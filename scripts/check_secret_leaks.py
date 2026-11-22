"""Check git-visible files for exact local secrets without printing their values."""
from pathlib import Path
import subprocess

from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
config = [item for path in (root / ".env", root / "deploy/.env.render") for item in dotenv_values(path).items()]
secrets = [value for key, value in config if value and len(value) >= 8
           and any(word in key for word in ("SECRET", "PASSWORD", "API_KEY", "DATABASE_URL"))]
demo = root / ".local" / "portfolio-demo-password"
if demo.exists():
    secrets.append(demo.read_text().strip())
paths = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root, text=True).splitlines()
findings = []
for name in paths:
    path = root / name
    if not path.is_file() or path.suffix.lower() in (".png", ".webp", ".jpg", ".gguf", ".zip"):
        continue
    text = path.read_text(encoding="utf-8", errors="ignore")
    if any(value in text for value in secrets) or ("-----BEGIN " + "PRIVATE KEY-----") in text:
        findings.append(name)
if findings:
    raise SystemExit("Possible secret exposure in: " + ", ".join(findings))
print(f"No exact local secrets found in {len(paths)} git-visible paths. Review new secrets separately.")
