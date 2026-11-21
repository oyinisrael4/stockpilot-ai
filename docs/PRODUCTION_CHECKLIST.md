# Production deployment checklist

This checklist prepares a deployment for review. No infrastructure has been provisioned and no paid service has been activated.

## Choose the deployment model

| Model | What runs where | Cost and practical limits |
| --- | --- | --- |
| A. Public portfolio demonstration | Static landing and screen captures on a static host. An optional separate authenticated Django/PostgreSQL demo contains fictional records. | A static deployment can fit a free tier. A hosted interactive demo needs a database, backups and access controls. Select the labeled deterministic fallback unless that host has its own AI runtime. |
| B. Fully hosted application with AI | HTTPS proxy, built frontend, Django, PostgreSQL, downloaded Qwen and Whisper on the hosting machine. Keep inference on loopback next to Django for the currently supported Ollama transport. | Software and models require no paid API. Compute, persistent disk, backup and operations still cost money. Budget a host with adequate RAM and measured CPU capacity; the current model process alone used about 2.9 GiB. A low-memory free web instance is a poor match for this workload. |
| C. Local business installation | The business computer runs PostgreSQL, Django, local Ollama and offline Whisper. Use a production WSGI service and HTTPS for shared-browser access. | Existing hardware avoids inference API charges. Power, sleep, disk failure, patching and tested off-device backups become operational responsibilities. Start with supervised single-user use based on the measured inference latency. |

A website deployed elsewhere cannot reach 127.0.0.1 on this Windows computer. With the present integration, that address refers to the deployed backend's own machine. Do not open port 11434 to the internet or add a public tunnel to Ollama. To support a separate inference host later would require an authenticated private transport change and a security review.

Render offers free static/web options, but free web services sleep after inactivity and have ephemeral local storage. Its free PostgreSQL databases have expiration limits, so they are unsuitable as the only copy of pilot data. A small paid web/database plan or a modest VPS is an option after reviewing a current quote and persistent-storage/backup requirements. Fly's trial should likewise not be treated as permanent free hosting. [Render free-service documentation](https://render.com/docs/free), [Fly trial documentation](https://fly.io/docs/about/free-trial/).

Recommended first release: static portfolio plus a password-controlled fictional demo, with hosted AI explicitly disabled until hardware and costs are approved. Record a real local AI/voice walkthrough alongside it. Keep the ordinary workspace database and credentials off the public demo.

## Build and startup gate

- [ ] Select a host, domain, operator and budget. Get approval before creating resources.
- [ ] Install a supported Python/Node/PostgreSQL environment. Upgrade packaging tools and run advisory scans.
- [ ] Install backend requirements-production.txt. It adds Waitress to the ordinary application dependencies.
- [ ] Build the frontend with npm ci and npm run build. Serve frontend/dist from the HTTPS proxy; Vite's development server is for local development.
- [ ] If deploying a demo, set VITE_STOCKPILOT_DEMO_URL to its actual HTTPS login URL. Use VITE_STOCKPILOT_CSRF_COOKIE=stockpilot_demo_csrftoken for the demo build only.
- [ ] Place secrets in the host's private environment/secret store, outside git and the web root. Avoid production secrets under the current OneDrive checkout.
- [ ] Set DJANGO_DEBUG=0, a unique randomly generated DJANGO_SECRET_KEY of at least 50 characters, explicit DJANGO_ALLOWED_HOSTS, STOCKPILOT_PUBLIC_URL=https://your-host, and the matching HTTPS DJANGO_TRUSTED_ORIGINS.
- [ ] Set STOCKPILOT_ALLOW_REGISTRATION=0 for the controlled public demo. The development .env.example enables registration and must be adapted deliberately.
- [ ] Configure PGHOST, PGPORT, PGDATABASE, PGUSER and PGPASSWORD. Use PGSSLMODE=verify-full and the provider's CA settings for a remote database.
- [ ] Use the migration operator role for migrate and createcachetable, then switch to the restricted runtime role.
- [ ] Run manage.py check --deploy --fail-level WARNING and makemigrations --check --dry-run under the actual production environment.
- [ ] Start scripts/serve_production.py from the repository root using the virtual environment Python. It binds 127.0.0.1:8000 by default, uses four threads, a 64-connection limit, a 2 MiB body cap and a 150-second channel timeout. Supervise and restart it with the host's service manager.
- [ ] Keep PostgreSQL and the WSGI listener accessible only to required local/private peers.

## HTTPS and proxy gate

- [ ] Adapt deploy/nginx.conf.example and run nginx -t on the host. The template is untested in a provisioned nginx/TLS environment.
- [ ] Reject unknown hosts in a default virtual host. Redirect HTTP to HTTPS and install a valid certificate with renewal monitoring.
- [ ] The proxy must overwrite forwarded headers. Waitress trusts forwarded protocol/address only from 127.0.0.1. Do not make the backend port public.
- [ ] The template routes only /api/ to Django and serves the frontend build. It contains no route to Ollama or PostgreSQL.
- [ ] Verify CSP, microphone permission, blob audio playback, local product artwork and HTTPS image URLs. Inline style permission supports existing chart styles; scripts remain restricted to same-origin.
- [ ] Secure cookies and SSL redirects are enabled by DJANGO_DEBUG=0. Enable DJANGO_HSTS_INCLUDE_SUBDOMAINS and DJANGO_HSTS_PRELOAD only after checking every affected subdomain and the preload requirements. The local deploy check enabled these for a dummy host, which does not validate your real domain.
- [ ] Install strict edge request/connection limits in addition to DRF's shared but non-atomic throttles. Adapt limits for reviewer traffic and proxy topology.
- [ ] Protect access/error logs, omit query strings, cookies, bodies and credentials, and set retention limits.

Use the versioned Django deployment checklist to review these decisions before publishing. [Django 5.2 deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/), [Waitress proxy arguments](https://docs.pylonsproject.org/projects/waitress/en/stable/arguments.html).

## PostgreSQL and recovery gate

- [ ] Create separate database/schema ownership, migration/backup and runtime roles. The generated development superuser is not the runtime role.
- [ ] Runtime needs CONNECT, schema USAGE, table SELECT/INSERT/UPDATE/DELETE and sequence USAGE/SELECT for application tables; it does not need superuser, CREATEDB or migration ownership.
- [ ] Configure SCRAM authentication and firewall/pg_hba rules for known peers. The existing local cluster uses SCRAM and only loopback host entries; remote TLS still needs host verification.
- [ ] Account for database connection limits. Inference uses a separate connection for a session advisory lock. Use a direct or session-pooled connection, not transaction-mode pooling, for this implementation.
- [ ] Monitor statement timeouts (30 seconds), lock waits (10 seconds), disk space and connection failures. Test legitimate workloads before adjusting limits.
- [ ] Schedule encrypted backups, protect manifests, keep a separate copy, and exercise the isolated restore workflow before each pilot milestone.
- [ ] Restore and inspect an archive on the actual destination infrastructure, not only this laptop.
- [ ] Retain source databases during cutover until balances and audit history are accepted.

## AI and audio gate

- [ ] For hosted deterministic demo mode, leave STOCKPILOT_AI_MODEL and STOCKPILOT_AI_API_KEY empty. The UI labels its limited capability.
- [ ] For local Ollama, use the downloaded stockpilot-qwen3:4b model and loopback /api/chat endpoint. scripts/run_local_model.ps1 disables cloud operation, limits loaded models and parallel execution to one, and limits the queue.
- [ ] Install Whisper weights once with scripts/setup_local_voice.py on the machine that runs Django. Requests use local files, CPU int8 and two threads.
- [ ] Verify local-model latency, busy/unavailable responses, real transcription and edited text before allowing a demonstration.
- [ ] Keep model files on persistent private storage. Do not assume an ephemeral free web filesystem preserves them.
- [ ] Reserve memory for the OS, PostgreSQL, WSGI, the speech model and the model process. A single-database shared inference lock deliberately trades throughput for predictable local memory use.
- [ ] Test proxy/request timeouts and memory limits under load. Closing the browser does not cancel server-side transcription already admitted.
- [ ] Never expose port 11434, model credentials or a model-control API through the public reverse proxy.

Ollama binds to localhost by default; verify the actual service's environment and listener, particularly if installed through a separate desktop application. [Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx).

## Authentication, demonstration and pilot gate

- [ ] Give reviewers separate accounts with the minimum role needed. Keep the seeded demo-owner password private. Use owner settings or an operator-created account to assign membership.
- [ ] Set STOCKPILOT_PUBLIC_DEMO=1 only with PGDATABASE=stockpilot_demo. The seed command also refuses any ordinary or populated database.
- [ ] Seed before production startup using the documented local workflow, then set production secrets and flags. Replace localhost product URLs with the demo's HTTPS asset URLs before hosting.
- [ ] Use fictional identities and transactions throughout the demo. Do not import real customer records into a publicly shared workspace.
- [ ] Configure SMTP and test delivery/recovery on the real domain. Reset delivery is synchronous; timing resistance and MFA remain future work.
- [ ] Review end-user onboarding, access revocation, error recovery, backup ownership and retention with the pilot business.
- [ ] Perform independent security review and sustained multi-user load testing before relying on the system for routine business operations.

## Operations and monitoring gate

- [ ] Monitor /api/v1/health/ through the actual HTTPS origin. It checks PostgreSQL reachability and returns a generic failure.
- [ ] Alert on failed health checks, restart loops, 5xx rates, unusual 429/503 rates, disk/memory pressure, backup age and certificate renewal failure.
- [ ] Verify the monitor triggers and reaches the operator. A configuration file alone is not an alerting test.
- [ ] Run clearsessions periodically and inspect shared cache growth. Update packages and repeat pip-audit/npm audit before releases.
- [ ] Record the deployed revision, migration version, environment names and operator procedures without copying secret values into the release report.
