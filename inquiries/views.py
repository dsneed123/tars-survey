from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.template.loader import render_to_string

from .forms import InquiryForm
from .models import Inquiry


def _send_inquiry_emails(inquiry):
    admin_email = getattr(settings, 'ADMIN_EMAIL', '')

    if admin_email:
        subject = f"New Inquiry: {inquiry.subject}"
        html_body = render_to_string('emails/admin_notification.html', {'inquiry': inquiry})
        text_body = render_to_string('emails/admin_notification.txt', {'inquiry': inquiry})
        send_mail(
            subject=subject,
            message=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[admin_email],
            html_message=html_body,
            fail_silently=True,
        )

    auto_reply_subject = "We received your inquiry"
    html_body = render_to_string('emails/auto_reply.html', {'inquiry': inquiry})
    text_body = render_to_string('emails/auto_reply.txt', {'inquiry': inquiry})
    send_mail(
        subject=auto_reply_subject,
        message=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[inquiry.email],
        html_message=html_body,
        fail_silently=True,
    )


def inquiry_form(request):
    if request.method == 'POST':
        form = InquiryForm(request.POST)
        if form.is_valid():
            inquiry = form.save()
            _send_inquiry_emails(inquiry)
            return redirect('inquiries:inquiry_success')
    else:
        form = InquiryForm()

    return render(request, 'inquiries/inquiry_form.html', {'form': form})


def inquiry_success(request):
    return render(request, 'inquiries/inquiry_success.html')
