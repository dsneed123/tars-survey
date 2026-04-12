from django.shortcuts import render


def landing(request):
    return render(request, "pages/landing.html")


def inquiry(request):
    return render(request, "pages/inquiry.html")


def services(request):
    return render(request, "pages/services.html")
