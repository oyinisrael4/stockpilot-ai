# Phase 8: public showcase and publication guide

Status: public launch approved by the owner on November 21, 2026. Publication is being prepared for `oyinisrael4/stockpilot-ai`; deployment is restricted to the static showcase on Cloudflare Pages Free. No local backend or inference service may be exposed. The public profile links are Israel's authenticated GitHub account and the website advertised by its public `israel-projects` repository.

## Two independent builds

| Build | Purpose | Required services |
| --- | --- | --- |
| `npm run build` → `frontend/dist` | Complete operational application | Django, PostgreSQL; optional local Ollama and Whisper |
| `npm run build:showcase` → `frontend/dist-showcase` | Public portfolio and fictional interactive sandbox | Static hosting only |

The static entry point is `frontend/src/showcase.tsx`. It never mounts the authenticated app, requests a session, calls business endpoints, records audio, or contacts a model. Hash routing and relative assets support both domain roots and GitHub repository subdirectories without server rewrites.

The landing page presents genuine screenshots previously captured from the isolated fictional Juniper workspace. Its six product images and hero are locally stored generated artwork; they are not photographs of real goods for sale. The screenshots are historic captures, not live data. Browser-demo values come from an explicitly authored public catalog and integer minor-unit calculations, never an export of real workspace records. The sandbox is a teaching example, not the Django accounting engine.

Try adding items, reviewing and cancelling checkout, confirming a fictional cash sale, viewing gross profit, cancelling/confirming a guided proposal, summarizing the resulting sample totals, and resetting. Eight sparkling waters exhaust that sample item's stock. Each tab is independent; reload erases changes. No sign-in, payment processing, persistence, database or arbitrary natural-language AI is offered publicly. Voice is an honest illustrated walkthrough with no simulated recognition.

## Local verification

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd run build:showcase
npm.cmd run test:showcase
npm.cmd run preview:showcase
```

Open http://127.0.0.1:5198/ and http://127.0.0.1:5198/#/demo. The showcase tests use installed Edge and need no database/model. On another OS change the test browser channel to an installed Chromium or install Playwright Chromium. The full application retains its existing separate test configuration.

Public profile links default to https://github.com/oyinisrael4 and https://israel-projects-one.vercel.app. Override with public HTTPS values in `frontend/showcase/.env`, following its `.env.example`. This dedicated Vite environment directory prevents importing the root application's `.env`. All `VITE_` values are public; never place credentials there.

## Zero-cost hosting choices, reviewed November 20, 2026

| Option | Fit and limits |
| --- | --- |
| Cloudflare Pages Free | Recommended static showcase. Free static requests; Free plan 500 builds/month, 20,000 files/site and 25 MiB per asset. Use the free `pages.dev` address. No Functions, database, inference, custom domain purchase or paid upgrade required. |
| GitHub Pages | Good public personal-project showcase. Published site limit 1 GB, soft bandwidth limit 100 GB/month; not for operating a commercial SaaS or facilitating commerce. This sandbox does neither. Hash routes support repository paths. Headers file is ignored by GitHub Pages; platform HTTPS still applies. |
| Vercel Hobby | Personal non-commercial portfolio only under its terms. Avoid presenting it as hosted commercial SaaS. Cloudflare is the simpler recommendation for this artifact. |

Sources: [Cloudflare limits](https://developers.cloudflare.com/pages/platform/limits/), [static requests](https://developers.cloudflare.com/pages/functions/routing/), [GitHub Pages limits and restrictions](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits), [Vercel Hobby](https://vercel.com/docs/plans/hobby). Verify terms again before launch; free plans can change. Do not enable usage-based services or buy a domain on a zero budget.

## Approval gate and publishing steps

The owner has explicitly authorized the public `oyinisrael4/stockpilot-ai` source repository and Cloudflare Pages Free static deployment. Authentication must be completed by the owner when needed. This authorization does not extend to paid services or exposing the full local application.

1. From the repository root run `.venv/Scripts/python.exe scripts/audit_publication.py` and `scripts/check_secret_leaks.py` with the same Python. Review every candidate file and the screenshots. The audit reports counts, file hashes and findings without printing keys. Its machine-specific report is ignored under `.local`.
2. Confirm repository visibility, intended repository name, source licensing and artwork attribution. No open-source license is assumed; choose one explicitly if you want reuse rights. Source publication without a license does not grant general reuse rights.
3. Review `git status --short`, then add only reviewed project paths, inspect `git diff --cached --stat` and `git diff --cached`, and create the first commit. There were zero commits and no remote when this phase began. Do not upload the workspace folder as a ZIP: it contains ignored private files locally.
4. After approval create the GitHub repository through GitHub, set its remote and push the reviewed commit. Rerun the history audit after committing. Do not force-push over an existing repository.
5. For Cloudflare Pages direct upload, upload **only the contents of `frontend/dist-showcase`**, using a Pages Free project. Alternatively connect the approved repository: root `frontend`, build `npm ci && npm run build:showcase`, output `dist-showcase`, Node 22.12+; no secrets, API origin or Functions. Keep the selected plan Free.
6. For GitHub Pages, an inactive manual workflow template is in `deploy/showcase-pages.yml.example`. Copy it to `.github/workflows/showcase-pages.yml` only after approval; choose Actions as the Pages source and manually dispatch. No workflow has been activated here.
7. Verify HTTPS, root and `#/demo` reloads, images, mobile navigation, GitHub/portfolio links and no API requests on the actual public URL. Test the deployed security headers; local Vite preview does not apply Cloudflare `_headers` rules. Save the published URL to the README only after it exists.

The static artifact includes a Cloudflare `_headers` file disabling network connections, forms, microphone, camera and framing. It applies only to the showcase build. It has no analytics, third-party script, font, cookies or tracking dependency. Public profile hyperlinks open only on user activation.

## Future full application hosting

The full application remains local and separate. Hosting its UI alone does not supply PostgreSQL, server authentication, transaction services, Ollama or Whisper. No component is exposed through a tunnel in this phase.

A later hosted pilot needs a Django WSGI host behind HTTPS, private PostgreSQL with off-device verified backups, SMTP, monitoring, secret management, deployment migration checks and a load budget. Consult [production checklist](PRODUCTION_CHECKLIST.md), [recovery procedures](DATABASE_RECOVERY.md) and [Phase 7 measurements](PHASE7_READINESS_REPORT.md). Current Ollama transport is loopback-only; inference must run next to Django or undergo a separately reviewed private-network integration. Do not point visitors at your Windows PC. Current CPU Qwen response times are roughly 20–53 seconds; Whisper takes roughly 1–4 seconds for the verification fixture. No free always-on inference infrastructure is promised. A supervised local installation remains the zero-hosting-cost full-feature option.
