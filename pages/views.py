from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from .models import Inquiry


def landing(request):
    return render(request, "pages/landing.html")


def inquiry(request):
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        company = request.POST.get("company", "").strip()
        repo = request.POST.get("repo", "").strip()
        team_size = request.POST.get("team_size", "").strip()
        use_case = request.POST.get("use_case", "").strip()

        if not name or not email:
            return render(request, "pages/inquiry.html", {
                "error": "Name and email are required.",
                "form_data": request.POST,
            })

        inquiry_obj = Inquiry.objects.create(
            name=name,
            email=email,
            company=company,
            repo=repo,
            team_size=team_size,
            use_case=use_case,
        )

        _send_admin_notification(inquiry_obj)
        _send_auto_reply(inquiry_obj)

        return redirect("pages:inquiry_success")

    return render(request, "pages/inquiry.html")


def inquiry_success(request):
    return render(request, "pages/inquiry_success.html")


def _send_admin_notification(inquiry_obj):
    admin_email = getattr(settings, "TARS_ADMIN_EMAIL", "admin@tars.ai")
    context = {"inquiry": inquiry_obj}
    subject = f"New TARS inquiry from {inquiry_obj.name} ({inquiry_obj.company or inquiry_obj.email})"
    body = render_to_string("emails/admin_notification.txt", context)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[admin_email],
        fail_silently=True,
    )


def _send_auto_reply(inquiry_obj):
    context = {"inquiry": inquiry_obj}
    subject = "We received your TARS early access request"
    body = render_to_string("emails/auto_reply.txt", context)
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[inquiry_obj.email],
        fail_silently=True,
    )
