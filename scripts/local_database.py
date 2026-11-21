"""Create or start an isolated, password-protected development cluster."""
import argparse
import os
import secrets
import shutil
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
local = root / ".local"
data = local / "postgres"
env = root / ".env"
port = "55432"
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--browser-tests", action="store_true", help="Also create the separate browser-test database.")
parser.add_argument("--demo", action="store_true", help="Also create the separate portfolio demo database.")
args = parser.parse_args()
local.mkdir(exist_ok=True)


def run(program, *args, **kwargs):
    executable = shutil.which(program)
    if executable is None:
        raise SystemExit(f"Add PostgreSQL's bin directory to PATH ({program} missing).")
    return subprocess.run([executable, *map(str, args)], check=True, **kwargs)


if not (data / "PG_VERSION").exists():
    if env.exists():
        raise SystemExit("Existing .env found. Use its database or move it before local bootstrap.")
    password = secrets.token_urlsafe(32)
    password_file = local / "postgres-bootstrap-password"
    with password_file.open("x") as handle:
        handle.write(password)
    try:
        run("initdb", "-D", data, "-U", "stockpilot", "--auth=scram-sha-256",
            "--encoding=UTF8", "--locale=C", f"--pwfile={password_file}")
    finally:
        password_file.unlink()
    with env.open("x") as handle:
        handle.write(
            f"DJANGO_DEBUG=1\nDJANGO_SECRET_KEY={secrets.token_urlsafe(64)}\n"
            f"PGHOST=127.0.0.1\nPGPORT={port}\nPGDATABASE=stockpilot\n"
            f"PGUSER=stockpilot\nPGPASSWORD={password}\n"
        )

if not env.exists():
    raise SystemExit("The development cluster needs its original .env file.")
status = subprocess.run([shutil.which("pg_ctl"), "status", "-D", str(data)],
                        capture_output=True)
if status.returncode != 0:
    run("pg_ctl", "start", "-w", "-D", data, "-l", local / "postgres.log",
        "-o", f"-h 127.0.0.1 -p {port}")

password = next(line.partition("=")[2] for line in env.read_text().splitlines()
                if line.startswith("PGPASSWORD="))
connection = {**os.environ, "PGPASSWORD": password}
databases = ["stockpilot"]
if args.browser_tests:
    databases.append("stockpilot_browser")
if args.demo:
    databases.append("stockpilot_demo")
for database in databases:
    result = run("psql", "-w", "-h", "127.0.0.1", "-p", port, "-U", "stockpilot",
                 "-d", "postgres", "-Atc", f"SELECT 1 FROM pg_database WHERE datname = '{database}'",
                 env=connection, stdout=subprocess.PIPE, text=True)
    if result.stdout.strip() != "1":
        run("createdb", "-w", "-h", "127.0.0.1", "-p", port, "-U", "stockpilot",
            database, env=connection)
print(f"Development database ready on 127.0.0.1:{port}.")
