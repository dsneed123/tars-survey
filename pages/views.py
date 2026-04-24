from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import cache_page


def health(request):
    return JsonResponse({"status": "ok"})


@cache_page(5 * 60)
def landing(request):
    return render(request, "pages/landing.html")


def services(request):
    return render(request, "pages/services.html")


# ---------------------------------------------------------------------------
# Docs pages
# ---------------------------------------------------------------------------

def docs_index(request):
    return render(request, "pages/docs/index.html", {"current_doc": "index"})


def docs_getting_started(request):
    return render(request, "pages/docs/getting_started.html", {"current_doc": "getting-started"})


def docs_worker_setup(request):
    return render(request, "pages/docs/worker_setup.html", {"current_doc": "worker-setup"})


def docs_api_reference(request):
    return render(request, "pages/docs/api_reference.html", {"current_doc": "api-reference"})


def docs_faq(request):
    return render(request, "pages/docs/faq.html", {"current_doc": "faq"})


def docs_changelog(request):
    return render(request, "pages/docs/changelog.html", {"current_doc": "changelog"})


# ---------------------------------------------------------------------------
# Status page
# ---------------------------------------------------------------------------

def status(request):
    # Check database connectivity
    try:
        connection.ensure_connection()
        db_ok = True
    except Exception:
        db_ok = False

    # Check worker heartbeats (any worker active in last 5 minutes)
    workers_online = 0
    try:
        from workers.models import Worker
        cutoff = timezone.now() - timezone.timedelta(minutes=5)
        workers_online = Worker.objects.filter(last_heartbeat__gte=cutoff).count()
    except Exception:
        pass

    workers_ok = workers_online > 0
    overall_ok = db_ok

    return render(request, "pages/status.html", {
        "db_ok": db_ok,
        "workers_online": workers_online,
        "workers_ok": workers_ok,
        "overall_ok": overall_ok,
    })
