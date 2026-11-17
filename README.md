<!-- about -->

# Tailorly

**Orders, measurements, invoices and staff pay for a tailoring shop**

Website: [dmi.tabrez.xyz/p/tailorly](https://dmi.tabrez.xyz/p/tailorly)

## Screens

### S01 · Sign in

Sign in as the owner or the employee

![S01 Sign in](design/screens/S01-sign-in/screen.png)

### S02 · Today

![S02 Today](design/screens/S02-today/screen.png)

### S03 · Orders

Find any order and see its status and balance

![S03 Orders](design/screens/S03-orders/screen.png)

### S04 · Order Detail

![S04 Order Detail](design/screens/S04-order-detail/screen.png)

### S05 · New order

Create a custom or ready-made order for a customer

![S05 New order](design/screens/S05-new-order/screen.png)

### S06 · Customers

Find a customer and see who owes money

![S06 Customers](design/screens/S06-customers/screen.png)

### S07 · Customer detail

A customer's details, measurements and orders

![S07 Customer detail](design/screens/S07-customer-detail/screen.png)

### S08 · My Work

![S08 My Work](design/screens/S08-my-work/screen.png)

### S09 · My Pay

![S09 My Pay](design/screens/S09-my-pay/screen.png)

### S10 · Staff

![S10 Staff](design/screens/S10-staff/screen.png)

### S11 · Reports

![S11 Reports](design/screens/S11-reports/screen.png)

### S12 · Production

![S12 Production](design/screens/S12-production/screen.png)

### S13 · Payments

![S13 Payments](design/screens/S13-payments/screen.png)

### S14 · Staff Report

![S14 Staff Report](design/screens/S14-staff-report/screen.png)

### S15 · Products

![S15 Products](design/screens/S15-products/screen.png)

### S16 · Work Plan

![S16 Work Plan](design/screens/S16-work-plan/screen.png)

### S17 · Production Record

![S17 Production Record](design/screens/S17-production-record/screen.png)

### S18 · Settings

![S18 Settings](design/screens/S18-settings/screen.png)

### S19 · Item Detail

![S19 Item Detail](design/screens/S19-item-detail/screen.png)

### S20 · Add item

Add one garment to a new order, or change it, with its product, price, options, measurements, materials, notes and photos

![S20 Add item](design/screens/S20-add-item/screen.png)

### S21 · Ai Assistants

![S21 Ai Assistants](design/screens/S21-ai-assistants/screen.png)
<!-- /about -->

## Development

### Requirements

- [uv](https://docs.astral.sh/uv/) (installs Python 3.14)
- PostgreSQL 18
- Node 24 (only for formatting and re-vendoring; not needed to run the app)

### Setup

```
uv sync
npm ci
cp .env.example .env   # then edit it
createdb tailorly
set -a; . ./.env; set +a
uv run python manage.py migrate
```

### Run

```
set -a; . ./.env; set +a
uv run python manage.py runserver
```

### Vendor

```
npm run vendor
```

Copies the pinned htmx and Alpine builds into `static/vendor/`, with their versions in the file names, and the Plus Jakarta Sans font files and licence into `static/vendor/fonts/`. The output is committed, so Node isn't needed to run the app.

### Format

Write:

```
uv run ruff format . && uv run ruff check --fix . && uv run djlint --reformat templates && npx prettier --write .
```

Check (CI runs this on every pull request):

```
uv run ruff format --check . && uv run ruff check . && uv run djlint --check templates && npx prettier --check .
```

### Test

```
uv run pytest
uv run pytest --cov --cov-report=term-missing
```

End-to-end tests use Playwright. Install the browser once, then run them; screenshots go to `artifacts/screens/`:

```
uv run playwright install chromium
uv run pytest -m e2e
```

### Styleguide and icons

`/styleguide/` shows every shared component and works only with `DEBUG=1` (add `?theme=dark` to preview dark). After changing `static/brand/mark.svg`, re-render the PNG icons:

```
uv run python scripts/render_icons.py
```

Amounts are in rupees (INR) with no tax.

---

<sub>Created with ❤️ by Dunder Mifflin agents</sub>
