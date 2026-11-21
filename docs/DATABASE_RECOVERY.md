# Database backup and recovery

The commands below operate on the database selected by your local environment. Keep backup files and manifests private. They include customer and financial records, session data and password hashes.

## Create a backup

From the repository root, with PostgreSQL's bin directory on PATH:

```powershell
.\.venv\Scripts\python.exe scripts/database_recovery.py backup .local/backups/workspace-YYYYMMDD.dump
```

Choose a new filename each time. The command refuses overwrites. It holds a read-only, repeatable-read snapshot while exporting the archive and hashing all business-table rows. Other business writes can continue. The archive is PostgreSQL's custom format and the companion manifest contains a checksum and per-table count/hash evidence.

For a real installation, write to an access-controlled encrypted volume outside the source checkout and its synchronization folders. Use a migration/backup role with the privileges pg_dump needs. Use TLS with certificate validation for a remote database. Backups should not inherit public static-file permissions.

## Verify a restore

```powershell
.\.venv\Scripts\python.exe scripts/database_recovery.py restore .local/backups/workspace-YYYYMMDD.dump --target stockpilot_restore_drill1
```

The target must be a new name beginning stockpilot_restore_. The restore command never drops or replaces a database. It checks the archive checksum before creating the target, restores with exit-on-error, then streams and compares the business-table row hashes. It leaves the restored database available for inspection. A failed restore may leave a partially created target; inspect it and choose a new target for the next attempt.

Test application compatibility against the isolated copy:

```powershell
$env:PGDATABASE = "stockpilot_restore_drill1"
.\.venv\Scripts\python.exe backend/manage.py migrate --noinput
.\.venv\Scripts\python.exe backend/manage.py check
```

Review reports, inventory balances, a sample receipt, customer balances and audit entries in this copy. Avoid performing new transactions in the source during an actual recovery cutover.

## Recover a service

1. Stop writes and put the affected service behind a maintenance response.
2. Identify the most recent verified archive and document the backup's timestamp and expected data loss.
3. Restore into a new isolated database, verify hashes, run migrations and inspect the application.
4. Save the previous database connection configuration securely. Change the application's PGDATABASE to the recovered name and restart the WSGI service.
5. Verify health, sign-in, key balances and audit history before allowing writes.
6. Preserve the previous database until the recovery has been accepted. Remove sensitive drill copies only under an explicit retention policy.

The runtime application role should not have CREATEDB or superuser privileges. The recovery command needs a separate operator role that can create the isolated target. Test that role and access to the backup before an incident.

A provisional pilot policy is daily encrypted backups, seven daily plus four weekly copies, with one copy on a separate device or provider. This is a proposed starting policy; set RPO/RTO with the business owner. Hosted PostgreSQL point-in-time recovery requires a provider-supported plan or a separately managed WAL archive. A successful small local drill does not establish the recovery time of a larger hosted database.

The Phase 7 drill restored all 23 business tables and 40 rows with matching hashes. The source database was preserved. Its archive took 2.562 seconds to create and 11.901 seconds to restore and verify. Both the ordinary workspace name and an existing drill target were rejected.
