# StockPilot AI — Reference Image and Design Direction

## Reference files
The five files in `design-references/` are AI-generated concept art for **visual inspiration only**:
- `00_All_Screens_Moodboard.png` — complete four-panel overview.
- `01_Dashboard.png` — sidebar/navigation, KPIs, chart, quick actions, stock health.
- `02_POS_and_Sales.png` — product cards, cart, quantity steppers, discounts and checkout.
- `03_AI_Assistant.png` — text chat, voice recording/transcription, editable sale proposals and confirmations.
- `04_Reports_and_Analytics.png` — period filters, financial KPIs, charts, recommendations.

The artwork may contain fictional people/businesses and inconsistent illustrative numbers. **Do not treat its figures or names as requirements or copy them into seeded data.** Product creator is **Israel Oyinlola**. Brand is **StockPilot AI**. Use fictional test businesses for the demo.

## Theme
- Background: #F7F9FE / #FFFFFF
- Sidebar: #0D1538; hover #20235D
- Primary: #4F46E5 / #2563EB
- Accent: #7C3AED / #06B6D4
- Positive: #10B981; warning: #F59E0B; negative: #EF4444
- Text: #17203C; secondary: #697189; borders: #E4E9F4
- Radius: 12–18 px, gentle shadows, restrained hover elevation
- Type: Plus Jakarta Sans/Sora for headings, Inter for body
- Layout: Desktop sidebar + header + responsive cards; collapsible mobile sidebar

## Interaction principles
- Three parallel entry modes: traditional UI, typed AI, optional voice-to-text. Every action has a non-AI path.
- Fancy visuals are intentional accents, not obstacles. Avoid overuse of WebGL, animated statistics, motion overload, auto-playing movement or cramped glassmorphism.
- Financial actions require confirmation and show the breakdown before posting. The database controls final amounts and stock.
- Use a quick, polished MVP design with complete working workflows before additional effects.

## Phase 6 production tokens

The references remain the source for product identity and working layouts. The current workspace uses quieter, solid surfaces so data, warnings and the next action carry the emphasis.

| Role | Token | Usage |
| --- | --- | --- |
| Workspace canvas and surface | #F4F5F8 / #FFFFFF | Background and bordered content regions |
| Navigation | #14162B | Workspace rail and public hero |
| Primary and focus | #5036C9 / #674AD8 | Primary action, branded icon and keyboard outline |
| Data and supporting text | #181B2D / #515B71 | Figures, labels and secondary information |
| Border and accent surface | #E0E3EC / #EFECFB | Separators and contextual assistant areas |
| Sales and expenses | #4934C2 / #168290 | Labeled chart series with an accessible period selector |

Use Inter or the local Segoe UI fallback. Display headings are compact and semibold. Give monetary figures tabular digits, use the locale and workspace currency, and reserve stronger borders for the primary financial result. Compact navigation and controls use an 8 px radius. Panels and dialogs use 13 px. Group controls and show enough space between sections to make reading order clear.

Charts pair color with labels and an inspectable date. Table headers stay distinct from rows. Use scrollable regions for wide tables on small screens. Maintain native keyboard behavior for forms and dialogs. The mobile drawer captures focus, closes on Escape and returns focus to its trigger.

Motion is limited to short feedback, dialog entry, loading placeholders and an assistant processing indicator. Reduced-motion preferences disable animations and transitions. The parcel illustration uses CSS geometry, with no external image request, animation loop or WebGL dependency.

## V2 art direction

The user-supplied StockPilot V2 screens take precedence over the original concept art. Use a light lavender navigation rail, violet active states, restrained borders, and navy typography. Group navigation by task. Reserve richer lavender treatments for contextual assistant interactions. Maintain one-line monetary values and inspectable chart data. Locally stored retail imagery supports the public hero and fictional catalog. Avoid illustrative figures within generated artwork or UI examples.

The assets and production prompts are documented in docs/PHASE61_ARTWORK.md.
