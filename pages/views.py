from django.http import JsonResponse
from django.shortcuts import render


def health(request):
    return JsonResponse({"status": "ok"})


def landing(request):
    return render(request, "pages/landing.html")


def inquiry(request):
    return render(request, "pages/inquiry.html")


def services(request):
    return render(request, "pages/services.html")
