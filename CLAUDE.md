# TARS Survey — tarsai.dev

Django web app deployed on Railway. Users sign up, add GitHub projects, submit tasks for TARS autonomous coding system.

## Current Status (2026-04-12)

### What's Working
- Full Django app with accounts, projects, tasks, members, billing, analytics, notifications, workers apps
- Dashboard shows user's projects with "Request TARS Code" buttons, active tasks, completed count
- Task submission forwards to local Mac Mini controller via Cloudflare Tunnel
- Controller API running on Mac Mini (port 8421) with visual dashboard
- Both repos pushed to GitHub: `dsneed123/TARS` and `dsneed123/tars-survey`

### What Needs Fixing (Railway Deploy)
**The site is NOT live yet.** Railway deploy fails because `DATABASE_URL` uses `postgres.railway.internal` which can't resolve.

**Fix:** In Railway dashboard, update `DATABASE_URL` env var to use the **public** PostgreSQL connection string instead of the internal one. Go to the Postgres service in Railway → Connect → Public URL. It'll look like:
```
postgresql://postgres:PASSWORD@monorail.proxy.rlwy.net:PORT/railway
```
Replace the current `DATABASE_URL` (which uses `postgres.railway.internal`) with this public URL.

After that, redeploy. The build should succeed now — debug_toolbar and migrate-during-build issues are already fixed.

### Cloudflare Tunnel
The tunnel URL is **temporary** — it changes on restart. Current one may be expired.
To restart on the Mac Mini:
```bash
cloudflared tunnel --url http://localhost:8421
```
Then update `TARS_CONTROLLER_URL` on Railway with the new URL.

For a permanent solution, set up a named Cloudflare tunnel with a fixed subdomain.

## Architecture

```
tarsai.dev (Railway) → Cloudflare Tunnel → Mac Mini:8421 (Controller API) → TARS daemon
```

- **Railway:** Django + PostgreSQL + Daphne (ASGI)
- **Mac Mini:** Flask Controller API (port 8421) + TARS daemon
- **Task flow:** User submits on website → `tasks/views.py` POSTs to controller → controller writes to queue.yaml → TARS daemon picks it up

## Key Files
- `tars_site/settings.py` — main config, env vars for everything
- `tars_site/urls.py` — URL routing
- `tasks/views.py` — task submission + controller forwarding (`_forward_to_controller()`)
- `members/views.py` — dashboard view
- `members/templates/members/dashboard.html` — main dashboard UI
- `railway.toml` — Railway build/deploy config
- `Procfile` — process definition (may be redundant with railway.toml)

## Railway Env Vars Needed
- `DATABASE_URL` — **use public PostgreSQL URL** (not internal)
- `SECRET_KEY` — Django secret
- `DEBUG` — currently `True` (set to `False` once stable)
- `DJANGO_SUPERUSER_EMAIL` — admin@tarsai.dev
- `DJANGO_SUPERUSER_PASSWORD` — admin password
- `TARS_API_KEY` — shared secret between website and Mac Mini controller
- `TARS_CONTROLLER_URL` — Cloudflare tunnel URL to Mac Mini
- `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` — for billing (optional for now)
- `RECAPTCHA_SITE_KEY`, `RECAPTCHA_SECRET_KEY` — for form protection (optional)

## Domain
- Domain: `tarsai.dev` (registered on Namecheap)
- DNS: Namecheap pointing to Railway via CNAME
- CSRF trusted origins include `tarsai.dev`, `www.tarsai.dev`, and Railway app URL
- HTTPS forced via `_ON_RAILWAY` detection in settings.py

## TARS API Key
```
431c1b93cd8c7b76b9ffded8ef84080bb589b6af2976db7f98710abe44a36059
```
Set identically on Railway (`TARS_API_KEY` env var) and Mac Mini (`tars.conf`).

## Dev Setup
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
Uses SQLite locally by default. Set `DATABASE_URL` env var to use Postgres.
