# Phase 7 security and reliability report

Verification date: 18 November 2026. The V2 frontend and financial service paths remain in use. This is a verified local readiness review, not a certification of an unprovisioned public deployment.

## Findings and fixes

| Finding | Resolution and evidence |
| --- | --- |
| DRF 3.17.2 had known request-parsing advisories | Upgraded the application requirement to 3.18.2. Added early limits for Accept headers and UTF-8 JSON. The installed dependency scan subsequently reported zero known vulnerabilities across 67 Python distributions. |
| Inference admission was not shared across WSGI workers | A nonblocking PostgreSQL advisory lock now admits one inference at a time per application database, shared by text and speech. A dedicated connection releases the lock on success, exception or connection close. Requests receive a busy response instead of building a queue. |
| Whisper had only a process-local lock | Retained the local model-initialization guard and added the shared admission budget. Its input stays capped at 45 seconds, 16 kHz mono PCM, about 1.44 MB, and is never saved by the endpoint. |
| Account throttles could change identity after authentication; default cache was process-local | Account limits now consistently use the effective client IP. Production uses a shared PostgreSQL cache table. The reverse proxy overwrites forwarding headers, and Waitress accepts them only from the local proxy. Arbitrary forwarded-for values do not alter DRF's throttle identity. |
| Sensitive API GET responses lacked an explicit private cache policy | API responses now carry no-store/private and no-cache headers. Microphone permission is limited to the same origin. |
| SMTP failures could distinguish existing reset accounts through a server error | Reset requests return the generic response even on delivery failure. Logs retain the failure class, not transport messages, addresses or reset tokens. SMTP timing still differs and is a remaining limitation. |
| Production configuration relied on local defaults | Production fails startup for weak secrets, missing/wildcard hosts, HTTP trusted origins, console reset email, or a public-demo flag on the ordinary database. Registration defaults closed in production. Reset links expire after one hour. |
| Request/search workloads needed defense-in-depth limits | API bodies are limited to 2 MiB at middleware/WSGI/proxy boundaries, headers and search/query sizes are bounded, reports have a per-user rate budget, and database statements/lock waits/connects have timeouts. |
| Catalog paging sorted all fixture rows | Added the measured composite catalog index. Its first-page SQL plan changed from a full scan and sort to an index scan. |
| Backup recovery had no verified procedure | Added a snapshot-consistent pg_dump workflow and a restore command that only creates a new isolated database. Archive checksums and every business-table row hash matched after restore. |

The request-parser advisories and patched versions are documented by the DRF maintainers. TokenProxy revocation was also reported by the scan; StockPilot uses Django sessions rather than DRF tokens, and the package upgrade includes its fix. [Accept parsing advisory](https://github.com/encode/django-rest-framework/security/advisories/GHSA-33wh-fxxf-88vv), [JSON charset advisory](https://github.com/encode/django-rest-framework/security/advisories/GHSA-3547-9m27-7rxg).

Local pip and setuptools were upgraded from 24.0/65.5.0 to 26.3/84.2.1 after their advisories were found. npm audit reported zero known frontend vulnerabilities. Scans cover known advisories at the verification time, not unknown vulnerabilities. The exact-local-secret scan found no matching keys, database password or demo password in git-visible files. Private env files, model artifacts, backups and backup manifests are ignored.

## Authorization and financial review

Authentication uses Django sessions with session rotation, password validation, CSRF-protected sign-in/registration/reset operations and session-authenticated mutations. Production cookies are Secure and session cookies remain HttpOnly. Password changes invalidate old session authentication hashes. Password reset tokens are single-use and expire after one hour. No wildcard CORS support is enabled.

TenantMixin checks membership before resource queries. Foreign workspace collection requests were tested across 19 endpoint groups. Detail serializers validate foreign product/category/customer/supplier references. Assistant conversations and proposals are additionally scoped to the signed-in account. Roles remain owner/manager for stock and expenses, cashier or above for selling/collecting payments, and read access for analyst/viewer. Reversals require owner/manager. Workspace membership administration requires owner.

The assistant's structured intent is validated before allowlisted backend tools run. Preparation and confirmation each enforce the current role. Explicit confirmation revalidates the preview and uses the manual transaction services. Prompt text has no SQL execution or direct write facility. Existing regressions cover prompt injection, ambiguity, price changes, expiration, cancellation, repeated confirmation and revoked roles.

Existing checkout transactions lock the business and product rows, preserve cost snapshots, and use unique request IDs. The suite covers overselling under concurrent requests, duplicate sales, weighted cost, mixed discounts/tax, split payments, receivables, partial/cumulative returns, refunds, voids, audit entries and local date boundaries. A new concurrent receipt test confirms one posting for a duplicate key and an untouched foreign workspace balance. The new index changes no ledger data.

## Measured performance

These are local measurements on the current 16 GB Windows computer, not internet latency or a multi-user SLA.

The isolated stockpilot_perf fixture contains 10,000 fictional products, 3,000 posted sales and 3,000 sale lines. Each API case ran six times with query capture enabled. Warm figures summarize the last five calls. Other local processes were active.

| Operation | Initial warm median | After index warm median | Queries |
| --- | ---: | ---: | ---: |
| Catalog page | 11.81 ms | 15.04 ms | 3 |
| Catalog substring search | 17.42 ms | 28.64 ms | 3 |
| 90-day report | 62.59 ms | 71.80 ms | 16 |
| 90-day insights | 307.71 ms | 547.54 ms | 44 |
| Sales page with nested records | 16.36 ms | 15.84 ms | 6 |

The index's SQL-only plan improved from 5.346 ms with 173 shared buffer hits to 0.033 ms with three hits. End-to-end runs were noisier and did not show an overall API speed-up. Substring searches still scan matching rows, and Insights still loops through the catalog and performs 44 queries. These are acceptable local test observations, with larger datasets and concurrent users still requiring load testing. The benchmark command is gated to the isolated performance database.

Built frontend measured in Edge, 1440 × 1000, localhost, without network/CPU throttling:

| Route | DOMContentLoaded | Largest observed paint | Ready including 500 ms network-idle wait | Long tasks |
| --- | ---: | ---: | ---: | ---: |
| Overview | 110 ms | 272 ms | 892 ms | 0 |
| POS | 63 ms | 524 ms | 1,008 ms | 0 |
| Insights | 70 ms | 400 ms | 880 ms | 0 |
| Assistant | 72 ms | 496 ms | 959 ms | 0 |

The temporary measurement server served the actual build and proxied the demo API. Measurements were single navigation samples; transfer was about 447–453 kB per route without compression, not a representative mobile field test. The JS bundle is 400.93 kB / 120.65 kB gzip, and CSS 43.47 kB / 10.73 kB gzip. No frontend dependencies or UI changes were needed for this phase. Existing browser tests exercise reduced motion, keyboard navigation, mobile overflow, POS, reports, assistant and real speech transcription.

| Local inference | Measured time |
| --- | ---: |
| Qwen first measured request, including model load | 52.734 s |
| Qwen next two requests | 19.888 s / 23.293 s |
| Whisper first measured request | 4.378 s |
| Whisper next two requests | 1.202 s / 1.088 s |

Qwen returned valid profit/continue/insights intents. Whisper processed the existing 2.8-second spoken water-sale fixture and verified the expected word. A process snapshot showed llama-server at roughly 2,993 MiB working set. Edge used about 647 MiB across eight processes; the snapshot also included test/development processes. This does not establish the peak memory of a dedicated deployed service. CPU Qwen is slow enough that public multi-user inference needs deliberate capacity planning.

## Recovery results

A backup of the existing local workspace database was restored into stockpilot_restore_phase7_final, without replacing the source.

- Archive size 116,555 bytes, backup 2.562 seconds, restore and verification 11.901 seconds.
- All 23 business tables and 40 business rows matched their snapshot row hashes.
- Targets named stockpilot and an already-existing restore database were both rejected.
- These timings describe this small database only. Sessions, schema and sequences are included in the archive; the hash comparison specifically verifies business tables.
- Private recovery artifacts and restored copies remain on this computer. Operators must control their access and retention.

See DATABASE_RECOVERY.md for operating commands and safeguards.

## Automated verification

- Full patched-backend suite passed 60 tests, including real Qwen conversations, spoken follow-up, inference concurrency, role/workspace checks and financial regressions.
- All six existing Edge browser journeys passed against the patched backend.
- Targeted final security checks cover the UTF-8 guard and redacted error filter.
- TypeScript and Vite production build passed. API schema validation and migration drift checks passed.
- A production-shaped settings check passed check --deploy. Loopback Waitress returned health/session HTTP 200, Secure CSRF cookies, private cache headers, and HTTP-to-HTTPS redirect 301.
- The real nginx/TLS/firewall configuration remains a deployment gate. Its template has not been exercised on a provisioned host.

## Remaining risks and limits

1. This is application-scoped tenant isolation without PostgreSQL row-level security. Direct database credentials are privileged. The generated development cluster user can create databases and must not become the production runtime role.
2. DRF cache throttles are shared but non-atomic and are not a denial-of-service perimeter. Use strict proxy limits and firewall rules, plus limited public-demo credentials.
3. Inference locking is shared by workers using one database and requires a direct or session-pooled PostgreSQL connection. Independent application databases or multiple services sharing a model need a coordinated inference worker. A transaction-mode pool is incompatible with session advisory locking.
4. Whisper cancellation drops the browser result but does not interrupt inference already running on the server. A 45-second upload limit and single inference slot bound this work. Qwen requests have a 120-second socket timeout. Neither is an externally validated hard real-time deadline.
5. Password reset delivery is synchronous. A timing distinction remains between known accounts and absent accounts; email ownership verification, MFA and an asynchronous mail queue are not implemented.
6. The public-demo owner can alter all fictional records. Use separate reviewer accounts, limit roles and registration, and restore a clean demo on an agreed schedule. Do not place business-pilot data in that database.
7. Error logs intentionally suppress exception details that may include SQL values. Operators need the timestamp/status/class and database audit trail to investigate. Do not turn on debug or request-body logging publicly.
8. The working path is under OneDrive. Check synchronization and permissions before keeping production secrets or backups there. The existing local dump is not encrypted by the script.
9. Real TLS, SMTP delivery, remote restore, host patching, monitoring alerts, retention rules, hardware failure, power loss and sustained public load are not verified here. No deployment or charge was performed.
10. The current Windows Ollama process is only reachable by its local backend. A hosted website cannot use it automatically. Optional hosted-provider code still exists, but this review and its live tests used the downloaded local model.

## Public-demo recommendation

Start with the static public landing and its actual fictional-workspace captures, then provide a separately authenticated, isolated interactive demo. For a small hosted demo, configure the deterministic fallback explicitly and keep Qwen disabled unless the hosting machine has its own installed local model and adequate RAM. The production checklist defines the remaining gates before publishing or inviting a real business.
