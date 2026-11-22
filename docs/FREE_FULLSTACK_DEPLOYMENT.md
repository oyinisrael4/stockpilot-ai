# Full application deployment: Render Free + Neon Free + Groq Free

## Verified public launch — November 22, 2026

Application: https://stockpilot-ai-p89q.onrender.com — choose Sign in, then Enter fictional demo. Additional static resource: https://stockpilot-ai-p89q.onrender.com/showcase/.

The running service was verified as Free. The existing unrelated service was unchanged; both share the workspace's free allowance. No domain, disk, Render database, paid model, billing upgrade or local tunnel was created.

Both public-hosted Edge tests passed in 1.7 minutes: real Groq sale interpretation, explicit/duplicate confirmation, Neon persistence, report follow-ups, actual Groq Whisper, microphone recording through a virtual test device, editable transcription, 390/1440 px captures, HTTPS, HTTP redirect, HSTS, Secure session cookie, API no-store and restrictive showcase policies. TLS verification remained enabled throughout. The container required an explicit system CA bundle for Neon; the local Node client used Windows trusted certificates.

Evidence: ignored `.local/hosted-live-tests.log`, `.local/cloud-live-verification.json`, and public `docs/screenshots/hosted-overview-{1440,390}.png`. Fictional verification transactions and audit trails were retained. These tests do not certify unrestricted availability or real-business readiness. The status narrative below describes the preparation stage; public-host verification is now completed as recorded here.

Status: cloud-provider integration and deployment configuration implemented. Local verification passed 70 backend tests (two opt-in local-model tests skipped), all six browser journeys against Django-served production React assets, both frontend builds, API schema validation and secret scanning. Real Groq/Neon verification passed sale interpretation, explicit and duplicate confirmations, persisted stock, multi-turn reports, actual cloud Whisper transcription and cancellation without writes, using production settings through an in-process HTTPS client. Fictional test transactions and audit trails were retained. Public Render ingress/browser checks remain separate and pending deployment. The static portfolio remains an additional resource at `/showcase/`.

## Architecture

One Render Free Docker web service builds the production React app and serves it through Django/Waitress at the same HTTPS origin. Neon stores application data, sessions, throttling cache and shared cloud usage allowances. Groq handles bounded intent extraction and speech recognition. Browser credentials, Groq keys and the database URL never enter frontend environment variables. The cloud image excludes Ollama, Whisper weights and the offline recognition dependency. Local requirements still support the original offline providers.

The hosted model uses Groq strict JSON-schema output, not Groq's built-in execution tools. Its validated intent is dispatched to StockPilot's existing authorized backend tools. The language model cannot calculate authoritative totals, execute SQL, choose arbitrary URLs or post transactions. Explicit confirmation, pricing validation, locking, audit history and idempotency still apply.

## Provider limits checked November 21, 2026

| Provider | Verified public offering and consequences |
| --- | --- |
| Render Free | 750 instance hours/workspace/month; sleeps after 15 idle minutes and may take around a minute to wake. Ephemeral disk, no free persistent disks or shell/predeploy jobs. Outbound bandwidth/build allowances apply; services/builds can be suspended without payment details. External API/database traffic may trigger suspension if excessive. Free SMTP ports are blocked. Choose Free, do not add payment details or approve a card authorization. |
| Neon Free | Current documentation lists 100 CU-hours/project/month, 1 GB storage/project, 5 GB public transfer/project/month and mandatory idle scale-to-zero. Older documentation/search results list 0.5 GB: use the limits actually shown in your console. Default 0.25 CU could consume 100 CU-hours in about 400 active hours; this is not always-on capacity. |
| Groq Free | Account-wide rate/token/audio limits apply; consult the organization's Limits page. Published Free table currently lists GPT-OSS 20B at 30 RPM/1,000 RPD/8,000 TPM/200,000 TPD, and Whisper at 20 RPM/2,000 RPD/7,200 audio seconds/hour/28,800 per day. The selected models must appear for your key. Do not upgrade to Developer or attach billing. |

Sources: [Render Free](https://render.com/docs/free), [Neon plans](https://neon.com/docs/introduction/plans), [Groq rate limits](https://console.groq.com/docs/rate-limits), [Groq billing](https://console.groq.com/docs/billing-faqs). Account-specific limits and availability take priority; free offerings can change.

Selected models: `openai/gpt-oss-20b` for chat and `whisper-large-v3-turbo` for speech. Groq currently documents strict structured outputs for GPT-OSS; schema validity is not a guarantee of correct business interpretation. Backend validation and confirmation remain mandatory. [Models](https://console.groq.com/docs/models), [structured output](https://console.groq.com/docs/structured-outputs), [speech](https://console.groq.com/docs/speech-to-text).

## Accounts and secrets — owner steps

1. Sign in to Render, Neon and Groq. Remain on Free. Stop if asked to purchase anything or authorize a charge.
2. Neon: create a project with only Postgres enabled, in AWS US East 2 (Ohio). Under Postgres database → Databases → Add database, create `stockpilot_demo` with the existing owner. The Render service will also use Ohio.
3. Neon Connect: select that database and turn pooling **off**. A direct endpoint is required because StockPilot uses session advisory locks; transaction pooling does not preserve their semantics.
4. Groq: create the `StockPilot AI Demo` API key; verify the organization is Free and both selected models are allowed.
5. `scripts/prepare_cloud_demo.py` creates the ignored `deploy/.env.render` with generated owner/visitor passwords and a Django secret. It refuses to overwrite an existing file. Paste `DATABASE_URL` and `GROQ_API_KEY` there locally, then set `STOCKPILOT_CLOUD_FREE_ONLY=1` only after confirming Free billing status. Never paste credentials into chat or commit the file.
6. Run `.venv/Scripts/python.exe scripts/check_cloud_setup.py`. It validates the isolated database and model listing, prints no credentials and sends no inference request. It strengthens Neon TLS to `verify-full`. On Windows, it exports public trusted CA certificates to ignored `.local/cloud-ca.pem` for libpq; Render Linux uses its system trust store.

The application cannot independently prove that a key's organization has never been upgraded to a paid plan. The explicit Free-only flag records the operator's confirmation; account billing controls are still essential. Application budgets are additional safeguards rather than a billing-plan detector.

## Render setup

After the verified code is pushed to GitHub, create a Render **Blueprint** from `oyinisrael4/stockpilot-ai`. Review `render.yaml`: exactly one web service, Docker runtime, **plan: free**, Ohio; no database, disk, cron, Worker, AI binding or paid resource.

Enter only the required private values in the Blueprint prompts: `DATABASE_URL`, `GROQ_API_KEY`, `STOCKPILOT_DEMO_PASSWORD`, and `STOCKPILOT_DEMO_VISITOR_PASSWORD`, copied privately from `deploy/.env.render`. Render generates its own Django secret. Do not paste the whole local environment file, especially blank hostname fields. The startup derives allowed hosts, CSRF origins and public HTTPS URL from Render's actual hostname. Auto-deploy is off; reviewed changes require a manual deploy.

The owner password remains private. A CSRF-protected **Enter fictional demo** button signs visitors into a restricted shared manager identity without publishing its password. Visitors share fictional records and demo conversations, which the interface explicitly discloses. This is not a place for real business or personal data. Public signup is closed. Managers cannot access owner-only workspace administration, and the shared identity cannot be renamed through the profile API.

Startup applies migrations, initializes the database-backed cache and seeds only an entirely empty `stockpilot_demo` database. Seeding requires explicit hosted opt-in, a valid owner password and a separate visitor password. Existing records are never reset or reseeded. A partially populated database causes a clear initialization failure rather than being overwritten. No demo owner credentials are committed.

The Render health-check path `/api/v1/live/` performs no database query. `/api/v1/health/` remains an on-demand database readiness check. Do not use uptime pingers or frequent database checks to defeat free-tier sleep or keep Neon compute unnecessarily active. Database connections close after requests. Migrations run at startup because free Render does not offer predeploy jobs.

Render ingress terminates TLS, and the Render-specific Waitress startup trusts one forwarded hop. Secure SameSite cookies and same-origin CSRF apply. The startup is restricted to the Render environment and cannot be used as a public local-Windows server. No CORS wildcard or third-party cookie workaround is introduced.

## Quotas, outages and disclosure

- One shared in-flight inference slot spans chat and speech across workers, using the direct Neon connection. Requests are rejected rather than queued.
- Default shared application allowance: 50 cloud chat requests/day, two/minute; speech 600 reserved seconds/day and 120/hour. Each recording is capped at 45 seconds/1.44 MB. Quotas are stored in PostgreSQL and survive restart. Failed requests retain reservations when the normal request transaction commits. Provider enforcement still applies first if another organization client consumes its quota.
- Groq calls have bounded response size and a 35-second socket timeout. No automatic retries, alternate model, alternate provider, billing upgrade, paid tools or untrusted endpoints are invoked. A missing key, unsupported model, quota exhaustion or outage produces a clear failure; manual operations remain available.
- Intent messages and limited conversational context go to Groq. Audio leaves the browser only when **Transcribe** is selected, passes through Django to Groq, and is not saved as a file or database recording. The transcript stays editable before sending. Cloud privacy notices distinguish this from local Ollama/offline Whisper; provider retention is governed by Groq's policies.
- Email account recovery is explicitly disabled for the public demo and returns a clear unavailable error. Render Free blocks SMTP ports. No email delivery is claimed. An authenticated owner can manage fictional access; private owner recovery uses the database/operator workflow. An HTTPS transactional-email provider would require a separately verified setup before email recovery can be enabled.

Free services may sleep, restart, throttle or suspend. This is a functioning public demonstration candidate, not an availability guarantee or a safe production home for real financial data. Keep the existing backup/restore procedure and export a backup before redeploys or pilot changes. No stored API keys are returned to the browser.

## Verification gates

Local new-provider tests stub network responses and verify strict schema handling, follow-up context, authorization, confirmation/retries, cancellation, quotas, actual WAV forwarding shape, no writes during transcription, same-origin asset isolation and liveness without database access. Existing financial and UI regressions remain required.

`scripts/verify_cloud_demo.py` uses the real private Groq key and isolated Neon database through Django's in-process HTTPS client with production settings. It initializes/seeds the empty demo, records exactly one fictional sale, checks duplicate confirmation, reads real report follow-ups, transcribes the private audio fixture with Groq, and checks cancellation. It retains the fictional transaction and audit trail. This does **not** claim public Render ingress/browser verification.

After Render is live, set `STOCKPILOT_HOSTED_URL` to its verified HTTPS origin and `STOCKPILOT_VOICE_WAV` to the local verification recording, then run:

```powershell
# From frontend/
npx.cmd playwright test --config playwright.hosted.config.ts
```

This opt-in test uses actual cloud requests and records one fictional sale. It requires available shared quotas and a quiet demo workspace. Verify TLS, cookie flags, security headers, mobile layouts, audio permission/transcript review, sale persistence and the static `/showcase/` resource on the real host. Add the public URL to README only after success. Docker image build and public-host checks must be reported separately from local success.
