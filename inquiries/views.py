from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.template.loader import render_to_string

from .forms import InquiryForm


def _send_inquiry_emails(inquiry, request):
    admin_url = request.build_absolute_uri(
        f"/admin/inquiries/inquiry/{inquiry.pk}/change/"
    )
    ctx = {"inquiry": inquiry, "admin_url": admin_url}

    # Notification to admin
    send_mail(
        subject=f"New inquiry from {inquiry.company_name} — {inquiry.contact_name}",
        message=render_to_string("emails/inquiry_notification.txt", ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.TARS_ADMIN_EMAIL],
        fail_silently=False,
    )

    # Auto-reply to inquirer
    send_mail(
        subject="We received your inquiry — TARS",
        message=render_to_string("emails/inquiry_autoreply.txt", ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[inquiry.email],
        fail_silently=False,
    )


def get_started(request):
    if request.method == "POST":
        form = InquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save()
            _send_inquiry_emails(inquiry, request)
            return redirect("inquiries:thank_you")
    else:
        form = InquiryForm()
    return render(request, "inquiries/get_started.html", {"form": form})


def thank_you(request):
    return render(request, "inquiries/thank_you.html")
