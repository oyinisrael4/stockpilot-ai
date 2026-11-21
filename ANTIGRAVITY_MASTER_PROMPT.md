# STOCKPILOT AI — COMPLETE GOOGLE ANTIGRAVITY BUILD PROMPT

> **Use:** Open a new StockPilot AI project/workspace in Google Antigravity. Add the entire `design-references/` directory from the accompanying ZIP to the project. Paste this prompt into the coding agent, ideally using its planning workflow (`/plan` if supported). Review its implementation plan, then tell it to implement each phase and verify its work. The reference pictures are **concept art**, not proof of working behavior or accurate business data.

---

## ROLE AND PRIMARY OBJECTIVE

Act as a senior full-stack software engineer, principal product designer, data engineer, and software test engineer working collaboratively. Build **StockPilot AI**, a polished, production-minded, fully functional, responsive inventory, sales, expense, purchasing, profit/loss, and AI business-assistance web application. It is a serious portfolio project by a developer named **Israel Oyinlola** intended to demonstrate outstanding full-stack engineering, intelligent workflow automation, and visually sophisticated UI/UX. Project author/creator credit belongs to Israel Oyinlola; never use names or businesses appearing in the illustrative images as assumed real identities.

### The defining product vision

A small-business owner must be able to operate the entire system in **three equally legitimate ways**:

1. **Traditional manual interface:** Navigate dashboards, product forms, inventory, sales/POS, suppliers, customers, purchases, expenses, returns, discounts, and reports with intuitive buttons, tables and forms. This must work completely without AI.
2. **Conversational AI through typed messages:** Ask about actual business records or describe a transaction using natural language, like chatting with an assistant.
3. **Conversational AI through recorded speech:** Press a microphone control, speak, review/edit the transcription, and submit exactly the same request to the same assistant, with the same permissions and confirmation rules.

The AI is not an isolated decorative chatbot. It understands authorized business intents, fetches data from actual APIs, performs deterministic calculations using the authoritative backend, proposes changes for user confirmation, and provides fact-grounded recommendations. However **no AI should be required** to accomplish ordinary inventory tasks.

**Example workflow:** User types or says “I sold 12 cartons of bottled water at ₦2,500 each; give the customer a five percent discount and mark it as bank transfer.” Assistant identifies the matching item, inventory unit, quantity, price and discount, asks for missing details or disambiguation as needed, and displays a clear editable transaction-preview card: gross ₦30,000; discount ₦1,500; total ₦28,500 (tax excluded unless configured). Only after an authorized user clicks **Confirm & Record** does the server create the sale, payment record, stock movements, financial ledger effects and audit trail. The sales form provides the same capability manually.

**Example analytical query:** “What was my profit from October 1 to October 31?” The server queries the database for the date range, uses historical costs and actual recorded expenses, returns gross and net profit separately, lists exclusions/assumptions, and links to the underlying report. The LLM explains the validated result; it must never fabricate figures.

---

## BEFORE YOU WRITE CODE — ANTIGRAVITY WORKFLOW

1. Inspect the workspace and all files in `design-references/`. Use the screenshots as mood, composition and navigation guidance; don't blindly reproduce placeholder names, arbitrary demo amounts or mathematical inconsistencies.
2. Produce an **Implementation Plan artifact**: architecture diagram, chosen dependencies, database schema, API contract, UI page map, AI command flow, security model, milestone task list and test plan. You may make reasonable engineering decisions and note them; only ask the human to decide something if truly blocking.
3. Follow dependency order: project skeleton → authentication/multi-tenant scoping → products and inventory → purchases/COGS → POS and expenses → deterministic reporting → AI chat and voice → polish, testing, documentation and deployment.
4. After implementation of each major milestone, **run** the actual application, compile/build, run lint/type checking and tests, verify user flows in a browser when tools allow, save screenshots/walkthrough artifacts, fix errors and document results. Do not equate “files created” with “finished product.”
5. Do not claim functionality implemented unless tested. If a provider key, internet access, hosting credential or feature is unavailable, provide an honest local/dev fallback and explicit setup instructions. Never invent test results or fake a deployed URL.
6. Work in small coherent commits, keep a task checklist, and preserve an audit of decisions in docs. Don't let missing optional AI provider credentials prevent the rest of the app from running.
7. When faced with a very large scope, complete a **genuinely usable MVP** first; then continue through feature phases instead of generating a visually impressive but nonfunctional shell.

---

## TECH STACK

**Frontend**
- React + TypeScript + Vite; React Router.
- Tailwind CSS; accessible headless component patterns such as shadcn/ui/Radix, with centralized theme tokens.
- TanStack Query for server state; React Hook Form + Zod for forms and validation; lightweight client state where justified.
- Recharts or another accessible, responsive charting library; Lucide icons; Framer Motion/Motion for restrained transitions.
- Optional React Three Fiber/Three.js for one or two subtle, progressively enhanced hero/empty-state visual accents only. Avoid heavy full-page WebGL. Honor `prefers-reduced-motion`, support low-power devices and provide non-3D fallback.
- Vitest, Testing Library, Playwright for relevant frontend tests.

**Backend**
- Python + Django + Django REST Framework; Django ORM and migrations.
- PostgreSQL as primary database. Use Python `Decimal`/database `NUMERIC`, never floating-point for money.
- Session-based authentication with CSRF protection for a same-origin app, or an appropriately secure cookie-based JWT design if architecture requires different origins. Explain the choice and enforce authorization on all endpoints. No insecure browser-local token storage.
- API schema/OpenAPI via a maintained compatible package, e.g. drf-spectacular.
- Service-layer functions for transactional operations, reporting and AI tools, so they can be tested independently of serializers/views.
- Optional Redis/background job queue only where genuinely required; do not add infrastructure just to inflate sophistication.
- pytest/pytest-django and factory-based test data.

**Development/deployment**
- Monorepo layout: `frontend/`, `backend/`, `design-references/`, `docs/`, `.env.example`, `README.md`, `docker-compose.yml` if useful.
- Containerized Postgres for reproducible local setup; sensible scripts for running development servers and migrations on Windows or other platforms.
- A realistic deployment path for frontend, backend and managed PostgreSQL, with health checks and no secrets in source control.
- Prefer compatible stable library versions verified at implementation time; lock/package dependencies reproducibly.

---

## VISUAL DESIGN DIRECTION (HIGH PRIORITY)

Use the four screenshot references stored in `design-references/`:

- `01_Dashboard.png`
- `02_POS_and_Sales.png`
- `03_AI_Assistant.png`
- `04_Reports_and_Analytics.png`
- `00_All_Screens_Moodboard.png`

Create **one cohesive premium visual system**, not four unrelated pages. The screenshots are inspiration rather than pixel-perfect specifications. The design should feel like a professionally crafted 2026 SaaS application that combines a clear, breathable dashboard with tasteful creativity:

- Deep-navy left navigation; warm near-white/slate main canvas; elegant indigo, violet, electric-blue and teal accents; restrained gradients and soft ambient glows.
- Example tokens (refine for contrast): navy `#0D1538`, indigo `#4F46E5`, violet `#7C3AED`, electric-blue `#2563EB`, cyan `#06B6D4`, teal `#10B981`, background `#F7F9FE`, card `#FFFFFF`, text `#17203C`.
- Headings: Plus Jakarta Sans or Sora; body: Inter. Readability, good spacing and meaningful hierarchy take priority over flashy effects.
- Rounded 12–18 px card corners, subtle shadows, clean hairline borders, sparing glassmorphism, polished icons, meaningful colour semantics (green good, red destructive/warning), clear loading and empty states.
- The left navigation includes Dashboard, Sales/POS, Products, Inventory, Purchases, Customers, Suppliers, Returns, Expenses, Reports, AI Assistant, and Settings. Use permissions to hide/disable unauthorized actions, while always enforcing permissions on backend too.
- Top navigation: business/location switch where appropriate, global search, alerts, current user, support/menu, mobile hamburger.
- Dashboard: five or six credible KPI cards, clear line chart, stock alert widget, recent transactions, top products, fast action shortcuts and a small AI insights panel.
- POS: fast product search, categories, optional thumbnail grid/table, cart panel, editable quantities and prices when allowed, line and cart discounts, subtotal, configurable tax, customer/payment selection, calculated total, and confirm/receipt actions.
- AI Assistant: a welcoming chat interface with clearly differentiated messages, suggestion chips, visible voice recording/transcription controls, transaction-review cards and confirmation/edit/cancel actions.
- Reports: date-range picker, comparison period, profit/loss cards, charts, category/product performance, expense breakdown, narrative recommendations grounded in the selected period, export controls.
- Mobile: genuinely responsive sidebar/drawer, cards and charts reflow cleanly, tables handle small screens, POS remains usable, chat input remains accessible.
- Accessibility: keyboard focus, labels, contrast, predictable navigation, reduced motion support, screen-reader feedback for important status changes, tooltips not required for basic usage.
- Three-dimensional styling: use slight card layering, lighting, icon depth, and one small decorative 3D visual where tasteful. NO distracting constantly spinning objects, inaccessible scroll hijacking, overanimated pages, oversized irrelevant hero renders or hidden functionality.
- No dead buttons, fake analytics, charts unrelated to the database, hardcoded success toasts, lorem ipsum in final flows, or fabricated transaction data outside an explicitly isolated demo seed dataset.

---

## CORE WORKFLOWS AND FUNCTIONAL REQUIREMENTS

### A. Onboarding, user accounts and business settings
- Register / sign in / sign out / reset password, and basic profile management with sensible rate limits and secure reset links in production.
- Create a business and select region, timezone, currency (default **NGN ₦**), tax setting, fiscal/reporting options and low-stock defaults. Default timezone `Africa/Lagos`; store timestamps timezone-aware in UTC.
- Business membership / roles: Owner/Admin, Manager, Cashier, Analyst or Viewer, with defined permissions per module. Business A must never read Business B's data by changing IDs.
- Optional branches/locations can be modeled minimally for expandability; if multi-location isn't fully supported, label it as future rather than simulating it.
- Business settings: logo, address, receipt footer, default product units, numbering prefixes, notification thresholds.

### B. Products and inventory
- Product CRUD: title, unique business-level SKU, barcode optional, category, unit, descriptions, optional image, cost and sales price, active status, reorder threshold, taxable flag and stock-tracking flag.
- Support unit clarity: unit/pack/carton/box where configured; do not silently treat cartons and individual items as interchangeable. Unit conversions must be explicitly modeled before use.
- Stock opening balances, purchase receipts, sales deduction, returns, waste/damage, manual adjustment with reason, and full stock movement log.
- Prevent unauthorized or accidental negative stock by default; permission-controlled override only with audit reason if configured. Prevent invalid quantities and overselling via server-side transactions and row locks.
- Low-stock and out-of-stock notifications backed by actual quantities.
- Import and export product catalogs via validated CSV, with dry-run preview and per-row error reporting. Avoid unsafe formulas in CSV export.

### C. Purchases and suppliers
- Supplier CRUD and purchase records with item quantities, unit purchase cost, discounts, shipping/landed cost where appropriately allocated, status and payment status.
- Goods receipt updates inventory quantity and valuation correctly; don't create duplicate stock movements if retried. Store actual purchase transaction date and cost.
- Select and document **weighted-average cost** as initial inventory costing methodology. Snapshot applicable COGS in each posted sale line at posting time, with clearly tested purchase/sale/return cases. Never recalculate historical COGS using a product's current cost price.

### D. Sales and POS
- Manual sale creation from searchable products with live stock display and cart, editable quantities, unit prices according to permissions, absolute or percentage discounts per line or order, optional configured taxes, customer, notes and payment type (cash, bank transfer, card as recorded tender type, credit). Do not imply card payments are processed without a real payment integration.
- Calculate subtotals, line/order discount allocations, tax, due, paid, change, balance and receipt consistently on backend. Reject negative charges, double discounts or inconsistent totals.
- Atomic posting: validate all lines + stock, create sale and line records with historical COGS, apply movements, record payment, create audit event, and return canonical receipt. Prevent double submission with idempotency keys/transaction identity.
- Sale states: draft/posted/void/refunded as appropriate; voids and returns must reverse stock/financial effects using separate traceable records rather than deleting posted transactions.
- Printable clean receipts; sales history, search, filters, detail view and exports.
- Credit sales/partial payments only if implemented with ledger and tests; otherwise mark deferred and do not use deceptive UI.

### E. Returns, discounts, expenses
- Returns tied to existing posted sales and quantities, with refund or credit adjustment, partial return support, optional restock decision, reason and audit history.
- Expense CRUD: category (rent, salaries, utilities, transport, etc.), amount, date, payment method, notes and optional attachment; modification permissions and auditable edits.
- Maintain strict separation between discounts, revenue, cost of goods sold, expenses, write-offs and other losses.

### F. Financial reports and analytics
- Date ranges with inclusive/exclusive boundary rules explicit in code; comparisons use equal-length prior periods where feasible. Reports must respect the business timezone.
- Financial definitions clearly visible:
  - `net_sales_revenue = posted gross sale line revenue - applied discounts - sales returns/refunds` (excluding tax collected where appropriate).
  - `gross_profit = net_sales_revenue - COGS` (adjust COGS appropriately for returns).
  - `net_operating_result = gross_profit - recorded operating expenses - documented stock losses/write-offs` (clearly specify any exclusions such as financing, depreciation, payroll liabilities, tax and unpaid purchases).
  - `gross_margin = gross_profit / net_sales_revenue`, if denominator > 0.
- Clearly label “Net Operating Result” instead of claiming audited net profit if accounting coverage isn't full. Negative values must be displayed honestly as loss; “How much did I lose?” should clarify whether user wants net operating loss, discounted sales, inventory shrinkage or expense totals if ambiguous.
- KPI cards for revenue, gross profit, net operating result, operating expenses, order count, stock value and low-stock count; date filters, trend charts, top products, inventory aging/turnover if enough data, returns and discounts analysis, exports CSV and optional PDF.
- Provide data drill-downs and a short “how calculated” explanation for each important financial KPI.
- Use dashboard and reporting backend services for ALL numerical outputs; don't let the frontend invent figures.

### G. AI assistant — real text input AND real voice input

**Goals:** answer business questions, explain data, propose safe business operations, and offer evidence-based recommendations.

**UI:** A chat page and accessible quick-launch panel. Text input, send button, suggested requests, message history, helpful clarification questions, microphone button, recording state, stop/cancel action, editable transcribed text, attachment of relevant previews, and visible assistant limitations.

**Example read-only requests:**
- “What were my sales last week?”
- “What was my gross profit between November 1 and November 8?”
- “Did I make a loss this month?”
- “Compare sales this month against last month.”
- “Which products are running low?”
- “What were my five most profitable products?”
- “Which expenses increased the most?”
- “What discount did I give on yesterday's sales?”
- “How can I reduce waste and improve margins?”

**Example action requests:**
- “Record a sale of 15 bottles of water at ₦250 each paid in cash.”
- “Add ₦12,500 transportation expense for today.”
- “Receive 25 cartons from Acme Supplies at ₦2,000 per carton.”
- “Adjust damaged stock down by three bottles, reason: breakage.”

**Implementation architecture:**
1. User's text or reviewed voice transcription reaches an authenticated `/api/v1/assistant/messages` endpoint.
2. A constrained intent extractor / model provider returns **strictly schema-validated structured parameters**, never executable SQL or arbitrary Python or unrestricted tool execution. Provide explicit allowlisted operations such as `get_sales_summary`, `get_profit_report`, `get_low_stock`, `get_top_products`, `get_expense_breakdown`, `build_sale_proposal`, `build_expense_proposal`, `build_purchase_proposal`, `build_stock_adjustment_proposal`, `recommend_actions`.
3. On read-only intents, backend checks authorization/business scope, executes deterministic reporting services, and sends those results to a response formatter. If the model produces prose, use actual returned figures only and cite source report/action IDs.
4. On mutating intents, create a **server-side proposal** containing parsed product references, prices, quantity/units, discounts, tax, expense types, payment method, totals and outstanding ambiguities. Show a clear editable user-facing preview. Enforce explicit permission checked **Confirm** endpoint; recheck stock, costs, prices and state at time of commit. Cancel must have no side effects. User messages never directly create or modify ledger entries.
5. If product names are ambiguous, price missing, wrong stock unit, unknown customer or unclear date range, ask a focused clarification rather than guessing.
6. Defend against prompt injection and misleading instructions embedded in business names, uploaded files, or user data. Never let the model override permissions, monetary calculation rules, business scoping or tool constraints. Add per-user throttling, timeout/error handling, cost logging and audited assistant actions.
7. Use a configurable LLM provider interface; environment-variable credentials only. If no provider key exists, the core app still runs; implement a **clearly labeled limited demo command parser** for a few deterministic sale and report examples rather than pretending a full AI model is active. Document real AI setup.
8. Voice: support HTTPS/localhost microphone permissions; use browser speech recognition where supported OR a clearly configurable server transcription adapter, with a fallback where users type. Always display the transcript for editing before sending. Handle no permission, unsupported browsers, silence, cancellation, network error and long recordings. Do not auto-commit a financial transaction when speech recognition ends. Optional text-to-speech response is lower priority.
9. AI recommendations must mention the actual evidence (e.g. sales decline of X%, 4 low-stock items, rising transport expense Y) and clearly distinguish suggestions from certain predictions. No unsupported causal claims.
10. Store AI conversation and approved action metadata with business scoping and reasonable retention controls; never put API keys or complete private datasets into front-end source.

### H. Notifications, search, activity
- Global product/customer/sale search, clear filter states, keyboard-friendly UI.
- Relevant alerts: low stock, oversell prevented, unconfirmed AI action, expiring goods if supported.
- Audit events for price edits, manual stock adjustment, sales posting/voiding, returns and AI-confirmed changes; show actor/time/reason.
- Pagination or cursor loading and server filtering for larger product catalogs.

---

## DATA MODEL AND BUSINESS RULES

Implement normalized, indexed database entities at minimum: `User`, `Business`, `BusinessMember`, `ProductCategory`, `Product`, `Unit`, `Supplier`, `Customer`, `Purchase`, `PurchaseLine`, `StockMovement`, `Sale`, `SaleLine`, `SalePayment`, `SaleReturn`, `ReturnLine`, `ExpenseCategory`, `Expense`, `AuditEvent`, `AIConversation`, `AIMessage`, `AIActionProposal` and relevant settings. Add `Warehouse` or `Branch` only if implemented consistently.

- Every tenant-owned entity includes `business_id`, and ALL queries filter by authorized membership. Enforce unique SKU per business and meaningful database constraints.
- Use numeric money fields with documented decimal places, consistent rounding, and quantity precision suitable for units/weight. All receipt computations must be reconciled server-side.
- Maintain immutable or reversal-based historical records for posted financial events. Do not silently edit previous ledger state.
- Use database transactions and row-level locking for concurrent inventory changes.
- Add created/updated timestamps, created_by / actor where relevant, sensible indexes, and foreign-key deletion protections for financial history.
- Ensure demo data is explicit and isolated; use realistic **fictional** Nigerian products (sachet water, bottled water, rice, drinks, cartons, packaging) and transactions to demonstrate dashboards; no personal information or actual businesses.

---

## DESIGN QUALITY, RELIABILITY AND SECURITY GATES

### User experience
- Distinct loading/empty/error/success states; skeletons where appropriate; error messages that tell the user how to recover.
- High-quality responsive navigation for desktop/tablet/mobile; no horizontal overflow except intentionally scrollable data tables.
- Functional sorting, pagination and filters; forms show validation and confirmation dialogs before destructive operations.
- Chart labels, legends and tooltips are clear; no decorative inaccurate percentages.
- Respect time zone, locale and NGN currency formatting (`₦1,234.50` or appropriate compact format). Allow alternate currency display settings without confusing conversion vs currency selection.

### Security
- Validate all client input server-side, enforce permissions at every endpoint and business scope at the query level; protect CSRF/CORS and sessions as configured.
- Use secure password storage, reset flows, rate limiting, permission-checked uploads, safe filenames and size limits, request logging without secrets, strict `.gitignore` and `.env.example`.
- Never expose secret keys, production credentials, private user data, or unrestricted arbitrary file operations. Sanitize logs, prevent CSV formula injection, disallow raw LLM SQL and shell tool execution.
- AI-confirm endpoints require authorization, non-expired proposals, server recomputation and idempotency.

### Tests — REQUIRED
At minimum, add executable automated tests for:
1. Auth and tenant isolation (business B cannot access A's products, sales or AI context).
2. Product CRUD validation and unique SKU rules.
3. Purchase receiving and weighted-average cost correctness.
4. Stock decrement and simultaneous-sale oversell prevention.
5. Discounts, tax configuration, rounding, receipts and idempotent sale posting.
6. Returns and expense posting reflected in reports correctly.
7. Gross profit and net operating result for a known fixture with exact expected values.
8. Date filtering, inclusive period boundaries, previous-period comparison.
9. AI text parser, ambiguous product clarification and safe transaction proposal lifecycle.
10. Unauthorized assistant action rejection and rejection of attempts to bypass confirmation.
11. Voice UX fallback for unsupported browser and permission denied.
12. Main Playwright user journey: sign in → create product → receive stock → sell with discount → record expense → ask profit → preview/confirm AI sale → verify stock and report.

**Mandatory acceptance scenario:**
- Create one product called `Bottled Water (75cl)` and receive 100 units at cost ₦150 each.
- Manually sell 10 units at ₦250 each with a 10% **order discount** and no tax. Assert net sales revenue = ₦2,250; COGS = ₦1,500; gross profit = ₦750; stock = 90.
- Record ₦300 transport expense. Assert net operating result = ₦450 for the selected period, if there are no other events.
- Ask the assistant by typed message for period profit, verify ₦750 gross and ₦450 net operating result with explanation.
- Speak or simulate recognized transcript “sell two bottles at 250 naira each”; verify a preview appears and stock remains 90 **until** Confirm. After confirming, stock becomes 88, a new sale exists exactly once, and audit history records the assistant-confirmed transaction.
- Test an ambiguous voice transcript, an unknown product, insufficient stock and an unauthorized account; all fail safely with helpful responses.

---

## BUILD PHASES — IMPLEMENT, VERIFY, THEN MOVE ON

**Phase 0 — Planning and scaffolding**
- Inspect screenshots; deliver architecture, routes, ERD, API plan, role matrix, design tokens, checklist, local setup; initialize repository and tests.

**Phase 1 — Working core**
- Complete auth, business settings, role enforcement, products/categories, opening stock and purchase receiving with true database integration; make UI attractive and functional.

**Phase 2 — Manual sales and financial reporting**
- Build full POS (discounts, payments, receipts), returns, expenses, stock movements and accurate dashboard/report services. This is the first genuinely usable demo.

**Phase 3 — Conversational typed assistant**
- Add authorized read-only reporting questions, transaction proposals, confirmation and evidence-based recommendations. Ensure exact calculations and no unauthorized mutations.

**Phase 4 — Voice interaction and UI excellence**
- Add voice recording/transcription review, graceful fallback, better animations, responsive polishing, performance/accessibility passes; optional tiny 3D accent.

**Phase 5 — Production hardening and delivery**
- Integration/e2e tests, seeded fictional demo, error handling, security review, deployment configuration, polished README and project case study, screenshots, brief demo script and limitations.

At the end of each phase, state: what was actually implemented, files changed, commands executed, tests passed/failed, screenshots generated, remaining scope and the specific next milestone. Do not silently drop requirements, disable tests, or mark simulated functionality complete.

---

## DELIVERABLES — EXPECTED FROM THE AGENT

- A working codebase with frontend/backend/DB integrated, not merely Figma-like screens.
- Reproducible developer setup (Windows-friendly commands), `.env.example`, migrations, seed command and optional Docker setup.
- Real database-driven dashboard, POS, products, stock, purchases, expenses, reports, AI chat and voice path as described.
- API schema, ERD/architecture notes, meaningful unit/integration/e2e tests and a known exact financial test fixture.
- A README showing: features, architecture, screenshots, setup, common errors, how to enable real AI, microphone limitations, privacy/security tradeoffs, deployment steps and explicitly incomplete features.
- Four or more verified real app screenshots (distinct from `design-references/` concept art), and a short walkthrough of the demo scenario.
- Clean professional source code, reusable components, consistent types, reliable error handling, clear naming and commits, without fake buttons or hardcoded business analytics.

## HOW TO START RIGHT NOW

First, read the project brief and the five files under `design-references/`. Produce a detailed `/plan`-style implementation plan and explicit milestone checklist. After reviewing the plan, set up the repository and build **Phase 1** into a working, tested application; continue iteratively through later phases, showing concrete test and browser verification evidence at each stage. Prioritize accurate data, usable manual workflows and safety before AI automation and before 3D decoration. **The project should look exceptional, but must actually work.**
