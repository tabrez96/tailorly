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

`SHOP_NAME` in `.env` is the first line of the invoice sent on WhatsApp. It moves to shop settings when that screen is built.

### Run

```
set -a; . ./.env; set +a
uv run python manage.py runserver
```

### MCP server

```
set -a; . ./.env; set +a
uv run python manage.py run_mcp   # http://127.0.0.1:8001/mcp
```

It answers only while the MCP server switch on Settings > AI assistants is on, with an access key from that page sent as `Authorization: Bearer <key>`. The tunnel routes `/mcp` to port 8001; set `MCP_SERVER_URL` to the public address so its host is accepted. Tools list only what the "What it can see" switches allow.

### First setup

Create the owner account (asks for a password; the phone number is the username):

```
uv run python manage.py create_owner --phone "98450 12345" --name "Shop owner"
```

Use this command rather than `createsuperuser`: only accounts made here get the owner role.

### Password reset

The owner resets a forgotten password on this machine with `uv run python manage.py changepassword <phone>` (the username is the 10-digit phone number). Employees ask the owner.

### Pages and sheets

Every page view returns `render_page(request, template, {"title": ..., "tab": ...})` from `core/pages.py`: requests with the `HX-Request-Type: partial` header get the fragment, everything else gets the full shell. Sheets extend `components/sheet_content.html` and answer `sheet_saved(response, "toast text")` on success. A sheet that must refresh part of the page answers `sheet_saved_swap(response, "toast text", "#target")` instead. Pass `subpage=True` in the page context for a Settings sub-page: the bottom navigation is hidden.

### Demo data and drafts

```
uv run python manage.py seed_demo          # an empty shop gets demo products, customers and orders in every status
uv run python manage.py delete_old_drafts  # removes draft orders older than a day; the backup timer runs it nightly in production
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

### Secret scan

CI scans the whole git history with [betterleaks](https://github.com/betterleaks/betterleaks) on every pull
request and fails on any finding. To run the same scan locally, install the version pinned in
`.github/workflows/ci.yml` and run from a full (non-shallow) clone:

```
betterleaks git . --redact --verbose --exit-code 1 --config .betterleaks.toml
```

Fake values in tests and examples are allowlisted in `.betterleaks.toml`, and a real secret anywhere else still
fails the build.

To update the pin, set `BETTERLEAKS_VERSION` in `.github/workflows/ci.yml` to the latest stable release and
`BETTERLEAKS_SHA256` to the sha256 of `betterleaks_<version>_linux_x64.tar.gz` from that release's checksums
file. Change both together.

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

## Deployment

### What runs

| Service                 | What                                                                    | Where                    |
| ----------------------- | ----------------------------------------------------------------------- | ------------------------ |
| `db`                    | PostgreSQL 18 (`postgres:18`), data in the `pgdata` volume              | not published            |
| `web`                   | gunicorn, 2 workers                                                     | 127.0.0.1:8000           |
| `mcp`                   | MCP server (`manage.py run_mcp`)                                        | 127.0.0.1:8001           |
| `tailorly-backup.timer` | (host systemd) `manage.py backup` then `delete_old_drafts` inside `web` | every night at 02:30 IST |

Cloudflare Tunnel (`cloudflared`) publishes one HTTPS hostname: `/mcp` goes to port 8001 and everything else to port 8000 (`deploy/cloudflared.example.yml`).

Media lives in `/var/lib/tailorly/media` and backups in `/var/backups/tailorly` on the host, mounted into the containers. The containers run as uid 10001.

### Install

Requires Docker Engine with the Compose plugin.

```
sudo install -d -o "$USER" /srv/tailorly
git clone <repo> /srv/tailorly
cd /srv/tailorly
sudo install -d -o 10001 -g 10001 /var/lib/tailorly/media /var/backups/tailorly
sudo install -m 600 deploy/production.env.example .env
```

Edit `.env`. Run every later command from `/srv/tailorly`.

### Production settings checklist

- `DEBUG=0`.
- A new `SECRET_KEY` (the command is in the example file).
- `POSTGRES_PASSWORD` from `openssl rand -hex 24` (hex only, because it goes into a URL). It only applies when the `pgdata` volume is first created; to change it later, run `ALTER USER` inside the `db` container.
- `ALLOWED_HOSTS` is the tunnel hostname; `CSRF_TRUSTED_ORIGINS` is `https://` plus the hostname.
- `SECURE_SSL_REDIRECT=1` and `SECURE_HSTS_SECONDS` set (Cloudflare sends `X-Forwarded-Proto`).
- `MCP_SERVER_URL` is `https://<hostname>/mcp`.
- `ASSET_VERSION` is passed at build time (see First start); it is not in `.env`.

Verify:

```
sudo docker compose run --rm web python manage.py check --deploy --fail-level WARNING
```

### First start

```
sudo ASSET_VERSION=$(git rev-parse --short HEAD) docker compose build
sudo docker compose run --rm web python manage.py migrate
sudo docker compose up -d
sudo docker compose exec web python manage.py create_owner --phone "98450 12345" --name "Shop owner"
sudo cp deploy/tailorly-backup.service deploy/tailorly-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tailorly-backup.timer
```

Other management commands (for example `changepassword <phone>`) run the same way: `sudo docker compose exec web python manage.py <command>`. Logs: `sudo docker compose logs -f web mcp`.

### Cloudflare Tunnel

Install `cloudflared`, then:

```
cloudflared tunnel login
cloudflared tunnel create tailorly
cloudflared tunnel route dns tailorly shop.example.com
sudo install -d -m 700 /etc/cloudflared
sudo install -m 600 ~/.cloudflared/<TUNNEL-ID>.json /etc/cloudflared/
sudo cp deploy/cloudflared.example.yml /etc/cloudflared/config.yml   # then edit the placeholders
sudo cloudflared --config /etc/cloudflared/config.yml service install
```

The credentials JSON stays in `/etc/cloudflared/`, never in the repo (`deploy/*.json` is git-ignored).

### Update to a new release

```
git pull --ff-only
sudo ASSET_VERSION=$(git rev-parse --short HEAD) docker compose build
sudo docker compose run --rm web python manage.py migrate
sudo docker compose up -d
```

Open phones see the new asset version and reload the shell once.

### Moving from the host install

One time only. Run from `/srv/tailorly`, with the checkout owned by the user who runs `git` (see Install). First create `.env` and carry the settings over, because Compose needs it for every step below:

```
sudo install -m 600 deploy/production.env.example .env
```

Edit `.env`: copy the values from `/etc/tailorly/tailorly.env` (drop `DATABASE_URL`, `MEDIA_ROOT` and `BACKUP_DIR`) and set `POSTGRES_PASSWORD` from `openssl rand -hex 24`. Then check it while the old services still run:

```
sudo ASSET_VERSION=$(git rev-parse --short HEAD) docker compose build
sudo docker compose run --rm --no-deps web python manage.py check --deploy --fail-level WARNING
```

Then stop and remove the old units and move the data across:

```
sudo systemctl disable --now tailorly-web tailorly-mcp
sudo rm /etc/systemd/system/tailorly-web.service /etc/systemd/system/tailorly-mcp.service
sudo docker compose up -d --wait db \
  && sudo -u tailorly pg_dump --format=custom --no-owner --no-privileges tailorly \
    | sudo docker compose exec -T db pg_restore -U tailorly --no-owner --single-transaction --exit-on-error -d tailorly \
  && sudo chown -R 10001:10001 /var/lib/tailorly/media /var/backups/tailorly
```

The dump goes straight into the new database, so no copy of it is left on disk. Run `sudo docker compose up -d` only if that chain succeeded. If it failed, fix the cause, run `sudo docker compose down -v` to clear the half-made database volume, and run the chain again.

Reinstall the backup unit as in First start, run `sudo docker compose run --rm web python manage.py migrate` (the imported database is still on the old schema), then `sudo docker compose up -d`. Stop the host PostgreSQL once the app works: `sudo systemctl disable --now postgresql`.

### Backups

Each night `manage.py backup` writes `tailorly-<stamp>.dump` and `tailorly-<stamp>-media.tar.gz` to `/var/backups/tailorly`, keeps the newest 14, and then `delete_old_drafts` runs. If the backup fails, the cleanup is skipped. Run one now and read the log:

```
sudo systemctl start tailorly-backup
journalctl -u tailorly-backup
```

Copy `/var/backups/tailorly` off the machine regularly.

### Restore from a backup

```
sudo docker compose exec -T db pg_restore --list < /var/backups/tailorly/tailorly-<stamp>.dump > /dev/null \
  && sudo tar -tzf /var/backups/tailorly/tailorly-<stamp>-media.tar.gz > /dev/null \
  && sudo systemctl stop tailorly-backup.timer tailorly-backup \
  && sudo docker compose stop web mcp \
  && sudo docker compose exec -T db dropdb -U tailorly tailorly \
  && sudo docker compose exec -T db createdb -U tailorly tailorly \
  && sudo docker compose exec -T db pg_restore -U tailorly --no-owner --single-transaction --exit-on-error -d tailorly < /var/backups/tailorly/tailorly-<stamp>.dump \
  && sudo rm -rf /var/lib/tailorly/media \
  && sudo install -d -o 10001 -g 10001 /var/lib/tailorly/media \
  && sudo tar -xzf /var/backups/tailorly/tailorly-<stamp>-media.tar.gz -C /var/lib/tailorly \
  && sudo chown -R 10001:10001 /var/lib/tailorly/media \
  && sudo docker compose start web mcp \
  && sudo systemctl start tailorly-backup.timer
```

Both files are checked before anything stops. If `pg_restore` fails after `dropdb`, the database is empty, the media is untouched and everything stays stopped. Fix the cause and rerun from `createdb`.

Try a restore first on a scratch database:

```
sudo docker compose exec -T db createdb -U tailorly tailorly_restore_check
sudo docker compose exec -T db pg_restore -U tailorly --no-owner -d tailorly_restore_check < <dump>
sudo docker compose exec -T db psql -U tailorly -d tailorly_restore_check -c "select count(*) from django_migrations"
sudo docker compose exec -T db dropdb -U tailorly tailorly_restore_check
```

---

<sub>Created with ❤️ by Dunder Mifflin agents</sub>
