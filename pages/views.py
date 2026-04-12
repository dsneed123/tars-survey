from django.http import JsonResponse
from django.shortcuts import redirect, render

from .models import InquirySubmission


def landing(request):
    return render(request, "pages/landing.html")


def inquiry(request):
    if request.method == "POST":
        InquirySubmission.objects.create(
            name=request.POST.get("name", ""),
            email=request.POST.get("email", ""),
            company=request.POST.get("company", ""),
            repo=request.POST.get("repo", ""),
            team_size=request.POST.get("team_size", ""),
            use_case=request.POST.get("use_case", ""),
        )
        return redirect("pages:inquiry_success")
    return render(request, "pages/inquiry.html")


def inquiry_success(request):
    return render(request, "pages/inquiry_success.html")


def health(request):
    return JsonResponse({"status": "ok"})
