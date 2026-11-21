# Phase 8 verification — November 21, 2026

The public portfolio is prepared locally and ready for publishing review. No external repository, hosting deployment, subscription, tunnel or billable service was created. The full application remains independent of the static sandbox.

## Delivered

- V2 landing page reused in a dedicated static build, with genuine fictional-workspace screenshots, capability descriptions and locally stored artwork.
- Author links: [verified GitHub profile](https://github.com/oyinisrael4) and [portfolio website](https://israel-projects-one.vercel.app), as advertised by the profile's public `israel-projects` repository. The portfolio URL was discovered from GitHub; an independent HTTP reachability check was blocked by this environment's connection errors, so public-site verification remains a launch check.
- Fictional Juniper catalog with interactive search, quantity removal, stock limits, review, cancellation, confirmation, transaction totals, gross profit and reset. All values are authored public examples or calculated from this tab's fictional sales. No operational workspace is exported.
- Guided assistant proposals and summary controls explicitly disclose no model connection. Voice is an illustrated workflow; it requests no microphone permission and makes no transcription claim.
- Dedicated public environment template, hash navigation, relative assets, restrictive static security headers and an inactive manual GitHub Pages workflow example. No publishing workflow has been activated.
- Repository/artifact audit and documented GitHub publication plus Cloudflare Pages Free/GitHub Pages hosting steps. [Publishing guide](PUBLIC_SHOWCASE.md).
- Corrected three malformed environment assignment lines found in the existing Ollama startup script. Its intended queue, parallel request and loaded-model limits are now valid PowerShell assignments. No inference transport or model was replaced.

## Automated verification

| Check | Result |
| --- | --- |
| Existing backend regressions | 60 passed; no skips, with real local Ollama and Whisper fixture checks enabled |
| Existing full-application Edge journeys | 6 passed, 4.3 minutes, including the configured offline transcription fixture |
| New static-showcase Edge journeys | 4 passed, 26.5 seconds, on the final Node-based verification server |
| TypeScript and both production builds | Passed |
| API schema validation and migration drift | Passed; no migration changes introduced |
| Publication audit | No known-local-secret or credential-pattern findings; no prohibited git-visible database/model/cache artifacts |

Private local logs are under `.local/phase8-backend-tests.log`, `.local/phase8-browser-tests.log`, `.local/phase8-showcase-tests-final.log`, `.local/phase8-schema.log`, and `.local/phase8-publication-audit.json`. They are excluded from publication. The backend suite's recorded elapsed time includes a long interruption/suspension during this working session; it is not a performance benchmark. See Phase 7 for measured performance.

The static tests exercise cancelled checkouts/proposals without mutations; repeated confirmation clicks without duplicate sample sales; calculated revenue/cost/gross profit; stock exhaustion; independent tabs; reload/reset; search/empty results; screenshot selectors; direct-route reloads; keyboard skip navigation; same-page anchors; not-found navigation; external link destinations; no backend or external request during sandbox interactions; security headers; and a GitHub-style `/stockpilot/` base path. They do not test real accounting behavior in the sandbox; the full backend regressions cover operational transactions.

Responsive checks cover 320, 390, 768, 1024, 1280 and 1440 px on landing and all four sandbox sections, with no document horizontal overflow. Reduced motion and keyboard skip focus were verified. Desktop/mobile captures were visually reviewed. A full screen-reader audit and public-host HTTP/header checks remain post-publication review items. No claim of complete WCAG certification is made.

The temporary Python verification server initially produced Windows connection resets while serving the JavaScript bundle. Replacing that local test utility with Node, with explicit MIME types and complete responses, resolved the failures; the final four journeys all passed. The deployable site itself remains static and needs no Node server.

## Publication audit scope

The repository has no ordinary commits or remote. It does contain 135 reachable file blobs in Codex snapshot tree references; these were scanned along with git-visible candidates. The audit checks exact local secret values, common credential/private-key patterns, excluded file names/types and every deployment file. It writes per-artifact SHA-256 hashes to the ignored local report. Public screenshots were reviewed as fictional Juniper data; they retain historic demo dates and figures rather than claiming live results.

The final artifact is about 1.25 MB across 14 files, including six product WebPs, the hero, three screenshots, HTML, JS, CSS and static headers. Its JS bundle is approximately 278.6 kB / 89.0 kB gzip. No database, API key, audio recording, model weights, source map or backend source is included. These static figures are build sizes, not internet loading benchmarks.

Secret-pattern scanning cannot prove the absence of every possible secret or private record. Review future additions and staged changes, rerun the audit after the first commit, and never upload the local workspace as an archive. No Git history was rewritten or erased.

## Screenshots

- [Public landing, desktop](screenshots/phase8-showcase-1440.png)
- [Public landing, mobile](screenshots/phase8-showcase-390.png)
- [Fictional checkout, desktop](screenshots/phase8-demo-1440.png)
- [Fictional checkout, mobile](screenshots/phase8-demo-390.png)

## Remaining launch decisions

Choose the public repository name/visibility and intended source license, then explicitly approve repository publication and/or static deployment. Cloudflare Pages Free with its included address is recommended; do not enable Functions, inference or usage-based add-ons. The optional GitHub Pages example is manually dispatched and inactive until deliberately installed. Verify actual public URLs, security headers, portfolio availability and mobile behavior after an approved deployment. Complete hosted application/AI infrastructure remains a separate future project governed by the [production checklist](PRODUCTION_CHECKLIST.md).
