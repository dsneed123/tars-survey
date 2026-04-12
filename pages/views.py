from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, F, ExpressionWrapper, DurationField
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Inquiry, InquiryNote


def landing(request):
    return render(request, "pages/landing.html")


def inquiry(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()

        if not name or not email:
            return render(
                request,
                "pages/inquiry.html",
                {"error": "Name and email are required.", "post": request.POST},
            )

        Inquiry.objects.create(
            name=name,
            email=email,
            company=request.POST.get("company", "").strip(),
            repo=request.POST.get("repo", "").strip(),
            team_size=request.POST.get("team_size", "").strip(),
            use_case=request.POST.get("use_case", "").strip(),
        )
        return redirect("pages:inquiry_success")

    return render(request, "pages/inquiry.html")


def inquiry_success(request):
    return render(request, "pages/inquiry_success.html")


@login_required
def dashboard(request):
    now = timezone.now()
    week_ago = now - timedelta(days=7)

    total = Inquiry.objects.count()
    new_this_week = Inquiry.objects.filter(created_at__gte=week_ago).count()

    won = Inquiry.objects.filter(status="won").count()
    closed = Inquiry.objects.filter(status__in=["won", "lost"]).count()
    conversion_rate = round((won / closed * 100) if closed else 0)

    # Avg hours from inquiry creation to first note (as a proxy for response time)
    avg_response_hours = None
    inquiries_with_notes = Inquiry.objects.filter(notes__isnull=False).distinct()
    if inquiries_with_notes.exists():
        durations = []
        for inq in inquiries_with_notes:
            first_note = inq.notes.order_by("created_at").first()
            if first_note:
                delta = first_note.created_at - inq.created_at
                durations.append(delta.total_seconds() / 3600)
        if durations:
            avg_response_hours = round(sum(durations) / len(durations), 1)

    statuses = [
        ("new", "New"),
        ("contacted", "Contacted"),
        ("qualified", "Qualified"),
        ("proposal", "Proposal"),
        ("won", "Won"),
        ("lost", "Lost"),
    ]

    pipeline = []
    for key, label in statuses:
        pipeline.append({
            "key": key,
            "label": label,
            "inquiries": Inquiry.objects.filter(status=key).order_by("-created_at"),
            "count": Inquiry.objects.filter(status=key).count(),
        })

    context = {
        "total": total,
        "new_this_week": new_this_week,
        "conversion_rate": conversion_rate,
        "avg_response_hours": avg_response_hours,
        "pipeline": pipeline,
        "active_status": request.GET.get("status", "new"),
    }
    return render(request, "pages/dashboard.html", context)


@login_required
def inquiry_detail(request, inquiry_id):
    inq = get_object_or_404(Inquiry, id=inquiry_id)
    notes = inq.notes.order_by("created_at")
    status_choices = Inquiry.STATUS_CHOICES
    context = {
        "inq": inq,
        "notes": notes,
        "status_choices": status_choices,
    }
    return render(request, "pages/inquiry_detail.html", context)


@login_required
@require_POST
def add_note(request, inquiry_id):
    inq = get_object_or_404(Inquiry, id=inquiry_id)
    note_text = request.POST.get("note", "").strip()
    if note_text:
        InquiryNote.objects.create(inquiry=inq, note=note_text)
    return redirect("pages:inquiry_detail", inquiry_id=inquiry_id)


@login_required
@require_POST
def update_status(request, inquiry_id):
    inq = get_object_or_404(Inquiry, id=inquiry_id)
    new_status = request.POST.get("status", "")
    valid_statuses = [s[0] for s in Inquiry.STATUS_CHOICES]
    if new_status in valid_statuses:
        inq.status = new_status
        inq.save(update_fields=["status"])
    return redirect("pages:inquiry_detail", inquiry_id=inquiry_id)
