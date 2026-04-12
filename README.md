# tars-survey

Marketing landing page for TARS — an autonomous coding agent that builds, tests, and ships code around the clock.

## Stack

- Django 5.x
- Bootstrap 5 (CDN)
- SQLite (dev)

## Quick Start

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Visit [http://localhost:8000](http://localhost:8000).

## Project Structure

```
tars_site/          Django project package (settings, urls, wsgi)
pages/              "pages" app
  views.py          landing + inquiry views
  urls.py           URL routing
  templates/pages/  landing.html, inquiry.html
templates/          base.html (shared layout)
```

## Pages

| URL | Description |
|-----|-------------|
| `/` | Marketing landing page |
| `/inquiry/` | Early-access inquiry form |
| `/admin/` | Django admin |
