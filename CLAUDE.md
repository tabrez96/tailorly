# Tailorly

Orders, measurements, invoices and staff pay for a tailoring shop

A small tailoring shop that makes custom clothes and also sells ready-made clothes keeps customers, measurements, orders, invoices, staff time and staff pay in separate places (or on paper). The owner wants one place for all of it. Scale: one shop, about 1 employee, about 100 orders a month. Evidence: the owner's own requirements and answers. No independent demand data was gathered; this is a validated-by-the-owner idea, not a market-validated one.

## Where things are
- `design/` is the design library: `brief.md`, `ux.md`, and `screens/S01-name/` (`screen.png` + `spec.md`, plus
  `states/*.png` for empty, error and other states). Screens have permanent IDs (S01, S02, ...). Tickets name the
  screens they build by ID. **Read the spec and look at the screenshot of every screen you build**; `ux.md` has the
  colors, type and spacing. Don't edit `design/`; the designer owns it.
- Design canvas (private and behind a login, so you can't open it; it's where the design gets reviewed): <!-- canvas -->not published yet<!-- /canvas -->
- Source code lives outside `design/`. Put it where the stack below says.

## Stack
<!-- stack -->
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
<!-- /stack -->

## How we work here
- Two long-lived branches: `develop` is where the work lands (every ticket's PR goes there); `master` is the
  release branch and only moves when the maintainer launches a release. Never commit to `master`.
- One ticket at a time, on its own branch (`dmi/t-<n>`), cut from `develop`. Small, focused changes.
- Each ticket becomes a pull request into `develop` that the maintainer reviews. A pull request changes **under 500
  lines** (code and tests; lockfiles and generated files don't count); anything bigger can't be reviewed, so split it
  into more tickets.
- Commit messages and pull request titles say only what the change does (`Show the running meeting under Now`): no
  ticket number and no product name.
- Prefer boring, proven tools. Don't add a dependency unless the ticket needs it.
- Keep platform-specific code thin and put logic in pure code with unit tests (aim for about 90% coverage). Code
  that can't run in the sandbox is verified by review plus those tests, and then by hand by the maintainer.
- Format with the formatter in the stack table before you say you're done, and keep its check in CI and next to the
  test commands. Never format files your change doesn't touch.
- Write tests for what you build, and run them before you say you're done. Document the build and test commands in the README under "Development".
- Never commit secrets, tokens or personal data. Don't put real credentials in examples.
- If the ticket is unclear or the design is missing something, ask the architect or designer instead of guessing.
