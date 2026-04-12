from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from inquiries.models import Inquiry

from .models import MemberProfile


@login_required
def dashboard(request):
    profile, _ = MemberProfile.objects.get_or_create(user=request.user)
    recent_inquiries = Inquiry.objects.filter(email=request.user.email)[:5]
    ctx = {
        "profile": profile,
        "recent_inquiries": recent_inquiries,
    }
    return render(request, "members/dashboard.html", ctx)
