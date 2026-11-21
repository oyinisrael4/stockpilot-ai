"""Offline backup and recovery drill. Restore only creates a new isolated database."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4
from time import perf_counter

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "stockpilot.settings")
import django
django.setup()
from django.conf import settings
import psycopg
from psycopg import sql

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=("backup", "restore"))
parser.add_argument("file", type=Path)
parser.add_argument("--target", help="New database name beginning stockpilot_restore_.")
args = parser.parse_args()
started = perf_counter()
config = settings.DATABASES["default"]
env = {**os.environ, "PGPASSWORD": config["PASSWORD"]}
base = {"host": config["HOST"], "port": config["PORT"], "user": config["USER"], "password": config["PASSWORD"]}
if os.getenv("PGSSLMODE"):
    base["sslmode"] = os.environ["PGSSLMODE"]


def run(tool, *arguments):
    executable = shutil.which(tool)
    if not executable:
        raise SystemExit(f"Add PostgreSQL bin to PATH ({tool} missing).")
    # pg tools can print connection details on error. Preserve diagnostics in a private operator terminal.
    subprocess.run([executable, "-h", config["HOST"], "-p", str(config["PORT"]), "-U", config["USER"],
                    *map(str, arguments)], env=env, check=True)


def file_hash(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def manifest(connection):
    result = {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'core_%%' ORDER BY tablename")
        tables = [row[0] for row in cursor.fetchall()]
    for table in tables:
        digest = hashlib.sha256()
        count = 0
        with connection.cursor(name="verify_" + table) as rows:
            rows.execute(sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY id").format(sql.Identifier(table)))
            for (row,) in rows:
                digest.update(row.encode())
                digest.update(b"\n")
                count += 1
        result[table] = {"rows": count, "sha256": digest.hexdigest()}
    return result

args.file = args.file.resolve()
manifest_path = args.file.with_suffix(args.file.suffix + ".manifest.json")
if args.action == "backup":
    if args.file.exists() or manifest_path.exists():
        raise SystemExit("Choose a new backup filename. Existing backups are never overwritten.")
    args.file.parent.mkdir(parents=True, exist_ok=True)
    with psycopg.connect(dbname=config["NAME"], **base) as source:
        source.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        snapshot = source.execute("SELECT pg_export_snapshot()").fetchone()[0]
        evidence = manifest(source)
        run("pg_dump", "--format=custom", "--no-password", "--snapshot", snapshot,
            "--file", args.file, config["NAME"])
    digest = file_hash(args.file)
    manifest_path.write_text(json.dumps({"source": config["NAME"], "archive_sha256": digest, "tables": evidence}, indent=2))
    print(json.dumps({"backup_seconds": round(perf_counter() - started, 3), "archive_bytes": args.file.stat().st_size}))
else:
    target = args.target or "stockpilot_restore_" + uuid4().hex[:12]
    if not target.startswith("stockpilot_restore_") or not target.replace("_", "").isalnum() or len(target) > 63:
        raise SystemExit("Restore target must be a new stockpilot_restore_ database.")
    expected = json.loads(manifest_path.read_text())
    if file_hash(args.file) != expected["archive_sha256"]:
        raise SystemExit("Backup checksum mismatch.")
    with psycopg.connect(dbname="postgres", autocommit=True, **base) as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname=%s", [target]).fetchone():
            raise SystemExit("Restore target already exists. Choose a new isolated name.")
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
    run("pg_restore", "--no-password", "--no-owner", "--no-acl", "--exit-on-error", "--dbname", target, args.file)
    with psycopg.connect(dbname=target, **base) as restored:
        actual = manifest(restored)
    if actual != expected["tables"]:
        raise SystemExit("Restored business ledger differs from the backup manifest.")
    print(json.dumps({"restored_database": target, "verified_tables": len(actual),
                      "verified_rows": sum(row["rows"] for row in actual.values()), "ledger_hashes_match": True, "restore_seconds": round(perf_counter() - started, 3)}))
