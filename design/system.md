# Tailorly — System design

## Overview
Tailorly is one place to run a small tailoring shop. The owner takes orders for custom and ready-made clothes, keeps each customer's measurements, tracks materials, invoices and payments (in rupees), sends invoices on WhatsApp, plans who makes what and in which order, and runs weekly staff pay with overtime. Employees sign in on their phone to start and end their day, time each garment they work on, and see what they have been paid. Reports show sales, profit, production, payments and staff time, and an optional MCP server lets the owner's AI assistant read (or, if allowed, update) shop data.

## Stack
Versions checked on 2026-11-16; exact patch versions are pinned in `uv.lock` and `package.json`.

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.14 | Chosen stack. 3.15.0 is out, but Django 6.1 only supports it from 6.1.3, so 3.14 is the current line the framework fully supports; the official MCP SDK is Python. |
| Framework | Django 6.1 | Current stable release (5.2 is the older LTS); auth, sessions, forms, CSRF, migrations and admin built in. Move to 6.2 LTS when it ships in April 2027 (security support for 6.1 ends December 2027). |
| UI model | Single-page app: one server-rendered app shell, htmx swaps the page content in place and pushes the URL | Chosen stack. No full page reloads after sign-in, but every URL still renders a complete page on a direct load, refresh or Back, so there is no client router or JSON API to keep in step. |
| Server interaction | htmx 4.0.1 (vendored; npm tags it `next`) | Chosen stack; current release. fetch-based, swaps 4xx responses (used for form errors), history restores by asking the server for the full page, explicit attribute inheritance. |
| Client state | Alpine.js 3.15 (vendored) with the official `@alpinejs/focus` and `@alpinejs/sort` plugins | Chosen stack; current release. Holds the timer tick, long-press, sheets, toasts and reorder state. Alpine initialises components in swapped content by itself. `focus` gives the sheet focus trap; `sort` (SortableJS inside) gives touch drag on S16, with Up, Down and Done as the keyboard path. |
| Database | PostgreSQL 18 on this machine | Chosen stack; current major (18.7). Partial unique constraints (one running timer per employee), check constraints, reliable `pg_dump`. |
| DB driver / config | psycopg 3, dj-database-url | Standard; one `DATABASE_URL` env var. |
| Photos | Local disk under `MEDIA_ROOT`, resized with Pillow (1600 px + 200 px thumb, JPEG) | ~100 orders a month fits on disk; served only through a login-checked Django view, never public. |
| App server | gunicorn (2 workers) behind Cloudflare Tunnel | Chosen hosting; no open ports, HTTPS from Cloudflare. |
| Static files | WhiteNoise with hashed file names | Serves CSS, the vendored htmx and Alpine files and the self-hosted Plus Jakarta Sans woff2 from Django with long cache headers; no extra web server, no bundler. |
| MCP server | `mcp` Python SDK (FastMCP), streamable HTTP, separate process `manage.py run_mcp` on port 8001 | Same code and ORM as the app; isolated from the web workers; the tunnel routes `/mcp` to it. |
| Hosting | This machine: systemd units for gunicorn, the MCP process and `cloudflared`; PostgreSQL 18 as a system service | Chosen hosting; no monthly server cost. |
| Backups | systemd timer: nightly `pg_dump` + media archive, 14 kept | The shop's whole record lives on one machine. |
| Packaging | uv (`pyproject.toml`, `uv.lock`); npm (Node 24 LTS) for Prettier and for pinning htmx and Alpine | Locked installs. `npm run vendor` copies the pinned htmx and Alpine builds into `static/vendor/`, which is committed; Node is never needed to run the app. |
| Tests | pytest, pytest-django, pytest-cov; pytest-playwright for end-to-end flows and 390x844 screenshots | Logic in pure functions with unit tests; Playwright proves the in-place navigation and key flows and gives the designer renders. |
| Formatter | Python: ruff (`ruff format`, `ruff check`); Django templates: djLint (`djlint --reformat`); CSS, JS, JSON, Markdown: Prettier | Handbook defaults; Prettier can't parse Django template tags, so templates use djLint, the standard Django template formatter. |
| CI | GitHub Actions with a PostgreSQL 18 service container | Runs the format checks and tests on every pull request. |

Time zone `Asia/Kolkata`, `USE_TZ = True`. Money is `DecimalField(12, 2)` in rupees, shown rounded to the rupee with Indian grouping (`₹1,42,600`) by one template filter. No tax fields anywhere.

## Single-page app shell
- **One shell per role.** After sign-in the browser loads one page: `shell.html` with the header area, `<main id="page">`, the floating bottom navigation (owner or employee), one `<dialog id="sheet">`, a toast region and an `aria-live` region. S01 Sign in is the only page outside the shell; signing in and out are full page loads.
- **Navigation.** Nav tabs, rows, back buttons and links inside `#page` use htmx (`hx-get`, target `#page`, `hx-push-url`). The view returns only the page fragment, with its `<title>` and the active nav tab, when the request is an htmx partial request (`HX-Request-Type: partial`); otherwise it returns the full shell with the page inside. One helper, `core.pages.render_page(request, template, context)`, decides this, so every view supports both. A direct load, refresh, shared link or Back (htmx 4 restores history by requesting the full page) always works.
- **After each page swap** the shell scrolls to the top, sets the active tab in an Alpine store, moves focus to the page's `<h1>` and announces the title. Sub-page Back buttons go back in history when the user came from inside the app, otherwise to the parent URL.
- **Sheets.** Sheet triggers load their form into `#sheet` with htmx (no URL change). An Alpine `sheet` component opens the `<dialog>`, traps focus with `x-trap`, closes on Escape or grab-handle drag and returns focus to the opener. A successful save closes the sheet and refreshes the parts of the page it changed (out-of-band swaps of the affected cards), plus a toast.
- **Forms.** Invalid forms answer 422 with the form re-rendered; htmx 4 swaps 4xx responses, so errors show next to the fields, the alert summary is announced and Alpine focuses the first field with an error. A successful create answers with the new page and `HX-Push-Url` (for example Create order lands on S04).
- **Client state in Alpine.** `x-data` components: `timer` (counts up from the server's `started_at`, re-syncs on every response, announces politely once a minute), `hold` (press and hold on owner nav tabs: 500 ms, vibration, saffron ring, then loads the tab's create page or sheet; a short tap just navigates), `reorder` (S16 drag with `x-sort`, and pick up with Up, Down, Done, each move announced), `photos` (picker, previews, upload with retry), `toast`. Server data stays on the server; Alpine holds only what is on screen.
- **Session and version.** An htmx request with an expired session gets `HX-Redirect` to S01. The shell sends its static asset version in a request header; when the server's version differs after a deploy, it answers `HX-Refresh: true` so the phone loads the new shell once. WhatsApp links open with `HX-Redirect` to `wa.me`.
- **Live screens.** S02 and S12 refresh their "right now" cards every 30 seconds with `hx-trigger="every 30s"` while visible; the timers tick locally in Alpine between refreshes.
- **htmx 4 settings**: attribute inheritance stays explicit (the default); the CSRF token is sent as a header set once on the shell; htmx and Alpine load from the app itself, with no third-party requests.

## Components
- `config/`: settings (all secrets and hosts from env), URLs, WSGI.
- `core/`: app shell templates (owner and employee), `pages.render_page`, the htmx middleware (partial vs full, expired session, asset version), design tokens (`static/css/tokens.css`, light + dark via `prefers-color-scheme`), components (large-title header, cards, hero, chips, pill buttons, segmented control, bottom sheet, floating nav), Alpine components (`static/js/app.js`: `timer`, `hold`, `sheet`, `reorder`, `photos`, `toast`), template filters (`inr`, `day` "Thu 12 Nov", `clock` "9:02 am", `duration` "2h 40m"), `ShopSettings` singleton.
- `accounts/`: sign in (S01), roles (owner, employee), `owner_required` / `employee_required` decorators, change password; landing page by role.
- `catalog/`: products, primary and secondary (S15); options and measurement fields.
- `customers/`: customers, saved measurement sets per garment, notes (S06, S07).
- `orders/`: orders, items, item photos, material lines, payments, invoice text, status changes (S03, S04, S05, S19, S20).
- `production/`: time sessions, estimates, queue ordering, assignment, reworks (S08, S12, S16, S17).
- `staff/`: employees, day records (attendance), pay and overtime maths, payouts (S09, S10).
- `reports/`: sales, profit, shop bills, production, payments, staff (S11 to S14); cost and gain maths.
- `today/`: S02 Today, S18 Settings hub.
- `assistants/`: MCP settings, access keys, activity log (S21) and the MCP server process.

Pure logic lives in plain modules with no request or ORM access where practical, each unit tested: `staff/pay.py` (day pay, overtime, week totals), `production/queue.py` (suggested order, late risk), `production/estimates.py` (usual time, rework estimate), `reports/costing.py` (item, rework and order cost and gain), `orders/invoice.py` (totals, balance, WhatsApp text), `core/money.py` (Indian grouping).

## Data model
- **User** (Django auth). **Employee**: user (one-to-one, nullable until a login is made), name, phone, photo, daily_wage, overtime_multiplier (default 1), active. The owner is a user in the `owner` group; employees are in `employee`.
- **ShopSettings** (one row): shop_name, shop_phone, monthly_running_costs, working_hours_per_month (208), pay_day (Saturday), mcp_enabled, mcp_scope_orders, mcp_scope_measurements, mcp_scope_money, mcp_scope_staff, mcp_can_change, hold_tip_seen.
- **Product**: name, kind (primary | secondary), type (custom | ready_made; primary only), usual_price (primary), unit (m | pcs | pair | set; secondary), cost_price, selling_price (secondary, per unit), billed_by_default (secondary), measurement_fields (JSON list of field names; custom only), active, created_at.
- **ProductOption**: product, name, kind (yes_no | choice), choices (JSON), material (FK Product, secondary, nullable), asked_when (at_order | when_done), position.
- **Customer**: name, phone, notes, created_at. **MeasurementSet**: customer, garment (product name), values (JSON field → inches), updated_at; unique (customer, garment).
- **Order**: number (sequential), customer, due_date, status (draft | open | in_progress | ready | delivered), paid_by (customer | free), assignee (Employee, nullable), invoice_last_sent_at, created_at, ready_at, delivered_at.
- **OrderItem**: order, position, product (nullable FK) plus snapshots: product_name, type, price, usual_price, option_answers (JSON), measurements (JSON copy), measurements_source; notes, status (not_started | in_progress | finished), estimate_minutes, estimate_locked, queue_rank (nullable = suggested), moved_by_owner, started_at, finished_at.
- **ItemPhoto**: item, image, thumb, position. First photo is the item's picture.
- **MaterialLine**: item or rework (exactly one set, check constraint), product (secondary, nullable) plus snapshots: name, unit, quantity, cost_price (nullable until known), selling_price, on_bill, bought_on, from_option (nullable).
- **Payment**: order, amount, paid_on, method (cash | upi | card | bank), note.
- **Rework**: item, number (R1, R2 per order), reason (fit | our_mistake | customer_change | repair), instructions, assignee, estimate_minutes, due_date, status, queue_rank, moved_by_owner, created_at, finished_at.
- **TimeSession**: employee, item or rework (exactly one), started_at, ended_at (null while running). Partial unique constraint: one open session per employee.
- **DayRecord**: employee, date, started_at, ended_at, edited_by_owner; unique (employee, date).
- **Payout**: employee, week_start (Monday), days_worked, day_pay, overtime_minutes, overtime_pay, amount, paid_on, method, note. A snapshot, so later edits to day records never change a recorded payout.
- **ShopBill**: date, description, amount.
- **AccessKey**: name, key_hash (SHA-256), prefix (first 8 chars, for display), created_at, last_used_at, revoked_at. **AssistantActivity**: key, tool, summary, kind (read | change), order (nullable), at.

Derived, never stored: invoice total (item prices + billed material selling prices), received, balance; hourly rate (daily_wage / 8); logged minutes; overtime; cost and gain; usual time per product; suggested queue position; late risk.

## Key flows
1. **Take a custom order (S05, S20, S04).** Owner holds the Orders tab or taps + New order; S05 swaps into `#page` and creates a draft order (hidden from lists) so photos can upload while it is filled in. Choose or add a customer. + Add item swaps in S20: pick a primary product (price fills from usual_price), answer options, measurements copied from the customer's MeasurementSet for that garment (editable on the item), materials picked from secondary products, notes, up to 3 photos (uploaded by the Alpine `photos` component, resized and stored). Add to order swaps back to S05 with the item listed; the draft keeps everything, so Back and refresh lose nothing. Set due date, Who pays (Free hides the advance), Assign to with an estimate pre-filled from the product's usual time and a queue hint, advance with method. Create order turns the draft Open, records the advance as a Payment, places the items in the assignee's queue and answers with S04 and its URL. Drafts older than a day are deleted by a management command run from the backup timer.
2. **Employee's day (S08).** Start my day creates today's DayRecord. Switch on an item closes any open TimeSession and opens one for that item; the first session locks the estimate and sets the item and the order to In progress. Pause closes the session. Finish item closes it and marks the item Finished (counted as produced today). End my day closes any open session and sets ended_at. Each is an htmx POST that returns the updated S08 fragment; the Alpine `timer` counts up from the server's `started_at` and re-syncs on every response, so a phone that slept shows the right time.
3. **Weekly pay (S10, S09).** For the chosen Monday–Sunday week, `staff/pay.py` turns DayRecords into days worked (start and end both set), day pay (daily_wage each), overtime minutes (minutes past 480 per day) and overtime pay (minutes / 60 × daily_wage / 8 × multiplier). The owner fixes a day's start or end on S10, then Record payout (a sheet) stores a Payout snapshot with date and method. S09 shows this week so far and the employee's past payouts.
4. **Order done and invoiced (S04).** Mark ready (a sheet) asks for any when-done option answers (saved as MaterialLines), then marks the order Ready and refreshes S04's status and invoice cards in place. If Send invoice on WhatsApp is ticked (enabled only with a customer phone), the server sets invoice_last_sent_at and answers `HX-Redirect` to `https://wa.me/91<phone>?text=<invoice text>`. Record payment adds a Payment (amount defaults to the balance). Mark delivered confirms if a balance remains.

## Testing approach
Commands (also in the README under Development and in CI):
- Format and lint: `uv run ruff format --check . && uv run ruff check . && uv run djlint --check templates && npx prettier --check .`
- Unit and integration tests: `uv run pytest` (uses `DATABASE_URL`, a local PostgreSQL 18; CI uses a PostgreSQL 18 service). Coverage: `uv run pytest --cov --cov-report=term-missing`, aim about 90% on the pure modules.
- End-to-end and screenshots: `uv run pytest -m e2e` (Playwright, Chromium, 390x844, light and dark). Each screen's test also checks the single-page rules: navigation from inside the app swaps `#page` without a full reload (a marker set on `window` survives), the URL updates, and a refresh or Back on that URL renders the same screen. Saves renders to `artifacts/screens/` for the designer to compare with `design/screens/`.
- Seed data: `uv run python manage.py seed_demo` creates a generic demo shop (owner, one employee, products, customers, orders in every status, a week of attendance) for QA and screenshots.
- QA checks per ticket: the acceptance criteria, the money rules against worked examples (800/day, 2h overtime = ₹200 at 1x), both themes, 44 px targets, keyboard path for sheets and reorder, focus moved to the title after each page swap.

## Open questions
- This machine must be on and online for the shop to use the app. Is it always on? If it sleeps or is switched off at night, employees can't start their day remotely.
- Backups are written nightly on this machine. Where should a copy go off the machine (an external drive, another computer, a cloud folder)? Without that, a disk failure loses everything.
- Owner password recovery: with no email, it is reset on this machine with `manage.py changepassword` (documented in the README).
