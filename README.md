# tars-survey — tarsai.dev

Django web app for TARS (Task Automation & Repository Steward), a SaaS platform where users submit coding tasks to an autonomous agent that builds, tests, and ships code via GitHub.

## What It Does

Users sign up, connect GitHub repos, and submit tasks through a ChatGPT-style dashboard. Tasks are forwarded to a Mac Mini controller running the TARS daemon, which invokes Claude CLI to implement the code, run tests, and open pull requests autonomously.

## Architecture

```
tarsai.dev (Railway/Django) → Cloudflare Tunnel → Mac Mini:8421 (Controller API) → TARS daemon → Claude CLI
```

- **Railway:** Django + PostgreSQL + Daphne (ASGI) + Redis (WebSocket channels)
- **Mac Mini:** Flask controller (port 8421) + TARS daemon
- **Task flow:** User submits task → `tasks/views.py` POSTs to controller → controller writes to queue.yaml → TARS daemon picks it up → Claude implements code → PR opened on GitHub

## Django Apps

| App | Purpose |
|-----|---------|
| `accounts` | Registration, login, profile |
| `members` | Dashboard, user home |
| `projects` | GitHub repo linking |
| `tasks` | Task submission, status tracking |
| `workers` | Worker node registration and management |
| `billing` | Stripe subscriptions and usage |
| `analytics` | Usage metrics and activity logs |
| `notifications` | In-app and email alerts |
| `teams` | Multi-user team access |
| `pages` | Marketing/public pages |
| `inquiries` | Early-access inquiry form |

## Stack

- Python 3.9+, Django 4.2+
- Daphne + Django Channels (ASGI/WebSockets)
- PostgreSQL (Railway) / SQLite (local)
- Redis (channels layer in prod)
- Whitenoise (static files), django-storages + S3 (media)
- Stripe (billing), django-ratelimit, bleach

## Quick Start

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Runs on SQLite by default. Set `DATABASE_URL` to use Postgres.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | Yes | Django secret key |
| `DATABASE_URL` | Prod | PostgreSQL connection string |
| `REDIS_URL` | Prod | Redis for WebSocket channels |
| `TARS_API_KEY` | Yes | Shared secret with Mac Mini controller |
| `TARS_CONTROLLER_URL` | Yes | Cloudflare tunnel URL to controller |
| `STRIPE_SECRET_KEY` | Billing | Stripe secret |
| `STRIPE_PUBLISHABLE_KEY` | Billing | Stripe publishable key |
| `STRIPE_WEBHOOK_SECRET` | Billing | Stripe webhook signing secret |
| `GITHUB_WEBHOOK_SECRET` | GitHub | Webhook validation |
| `GITHUB_TOKEN` | GitHub | GitHub API token |
| `AWS_STORAGE_BUCKET_NAME` | Media | S3 bucket for uploads |
| `AWS_ACCESS_KEY_ID` | Media | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | Media | AWS credentials |
| `RECAPTCHA_SITE_KEY` | Forms | reCAPTCHA site key |
| `RECAPTCHA_SECRET_KEY` | Forms | reCAPTCHA secret |
| `EMAIL_HOST` | Email | SMTP host |
| `EMAIL_HOST_USER` | Email | SMTP user |
| `EMAIL_HOST_PASSWORD` | Email | SMTP password |
| `DEBUG` | | Set to `False` in production |

## Deployment (Railway)

1. Connect this repo to a Railway project
2. Add a PostgreSQL service and a Redis service
3. Set all required env vars (use the public PostgreSQL URL, not the internal one)
4. Railway runs: `pip install` → `collectstatic` → `migrate` → `daphne` on `$PORT`
5. Health check: `GET /health/` with 300s timeout

See `railway.toml` for the full build/start config.

## Controller Connection

The Mac Mini controller must be reachable via a Cloudflare tunnel:

```bash
cloudflared tunnel --url http://localhost:8421
```

Set `TARS_CONTROLLER_URL` on Railway to the tunnel URL. For a permanent URL, configure a named Cloudflare tunnel with a fixed subdomain.

## API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health/` | GET | Health check (no auth) |
| `/tasks/<id>/status/` | GET | Task status |
| `/workers/register/` | POST | Worker node registration |

Controller requests use `X-API-Key: <TARS_API_KEY>` header.

## Tests

```bash
pytest
pytest --cov=. --cov-report=term-missing
```
