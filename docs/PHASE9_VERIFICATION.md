# Phase 9 — verified public demo refinement

Verified November 22, 2026 on https://stockpilot-ai-p89q.onrender.com.

## Registration and portfolio scope

Production registration remains disabled at both API and UI. The public registration page explains that commercial onboarding is not available and directs visitors to the fictional interactive demo. The landing and login links reflect that status. Visitors can still enter the shared demo without creating an account.

Local registration remains functional. Password confirmation is required in frontend and backend, mismatches display “Passwords do not match”, both fields have accessible show/hide controls, and password rules remain enforced by Django. Invalid submissions create no partial workspace/account records. Tests cover independent membership, tenant isolation, matching/mismatched passwords, invalid inputs and the closed production endpoint.

## Conversational change and safeguards

The previous cloud model only selected fixed intents; backend templates supplied its answers. Connecting Groq therefore did not create an open-ended response-generation path. The deployed assistant now has an analysis path over bounded, workspace-scoped backend insights, previous user messages and assistant answers. It can provide contextual suggestions, explanations and clarifying guidance; greetings and unseen business questions are not restricted to a phrase list.

Groq GPT-OSS 120B is selected on the existing Free account after live comparison showed better schema adherence than the smaller model. It writes qualitative guidance constrained by a structured output schema. Financial findings are rendered directly from backend evidence: a model citation alone is insufficient to establish a financial interpretation. Exact numerical values remain backend-owned in the supporting records. A regression test proves that a contradictory model claim cannot override recorded findings. Suggestions and limitations remain explicitly labelled. Model reasoning can still be imperfect; suggestions are advisory and are not guarantees about demand or business outcomes.

Malformed, uncited or unsupported responses fail validation. A narrowly bounded normalization accepts only omitted unspecified intent details as empty strings, then validates the entire intent; unknown fields and operations are rejected. This does not invent prices, relax permissions, retry a paid model, or bypass confirmation. Provider outages, rate limits, quota exhaustion and invalid responses remain distinguishable from unsupported requests.

All write requests retain the existing authorization, previews, explicit confirmation, stock locking, audit and idempotency services. General explanations have no write path. Typed and edited spoken messages share the conversation workflow. Offline Whisper remains operational. Local Ollama retains its existing model-assisted intents and deterministic backend insights; the new free-cloud narrative generation is not silently substituted into offline mode.

## Verification evidence

- Full backend suite: 80 tests discovered, 78 passed, two opt-in local-LLM tests skipped. This run included actual offline Whisper transcription. Earlier final targeted cloud/registration/finding tests also passed.
- Ten local Edge browser journeys passed against production React assets served by Django, including password controls, registration, closed-registration messaging, financial workflows, assistant confirmation, keyboard/mobile layout and microphone fallback.
- Both hosted end-to-end journeys passed: real cloud chat, contextual report follow-up, explicit/repeated sale confirmation, Neon persistence, actual Groq Whisper, browser microphone recording through a test device, editable transcription, mobile/desktop layout, HTTPS, cookies and security headers.
- A separate public registration check passed: no active registration form, explicit portfolio explanation, API rejection with valid CSRF, functional demo entry, and 390/1440 px screenshots.
- The production TypeScript/Vite build, schema validation and secret audit passed. No API keys, database credentials, model weights or local recordings were published.

The public natural-language sequence passed all ten requested questions and an unseen shelf-space question. It included improvement, overall performance, declining profit, restocking, sales growth, product profitability, next-week priorities, simpler wording, last month and greeting/capability questions. Manual review then caught a contradictory financial interpretation; the renderer was strengthened so model prose cannot establish authoritative financial findings. The final deployed build was rechecked with improvement, simplification and last-month turns, all passing with backend-rendered findings. The full read-only conversation verification is reproducible with `python scripts/verify_public_conversation.py --live`; it consumes the shared free allowance and intentionally paces requests.

Private verification logs/results are ignored under `.local`: `phase9-public-check.log`, `phase9-public-conversations.json`, `phase9-final-check.log`, `phase9-final-conversations.json`, `phase9-final-backend.log`, `phase9-browser-final.log`, `phase9-hosted-browser.log`, and `phase9-public-registration.log`. Fictional conversations and verification transactions retain their history rather than being erased.

## Remaining limitations

Free Render/Neon services can sleep or suspend. Groq and application quotas apply. A full analytical turn currently uses an intent request and an explanation request; the shared two-requests/minute allowance therefore requires pacing. The default daily application allowance remains conservative; testing consumed much of the day’s allowance. There is no paid fallback or automatic upgrade. Public demo records and the visitor identity are shared, so visitors must not enter private information. Email recovery remains disabled. This portfolio verification does not certify real-business production readiness or unlimited AI availability.

[Public registration — desktop](screenshots/phase9-registration-1440.png) · [mobile](screenshots/phase9-registration-390.png).
