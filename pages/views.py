from django.shortcuts import render


def landing(request):
    return render(request, "pages/landing.html")


def inquiry(request):
    return render(request, "pages/inquiry.html")


def about(request):
    return render(request, "pages/about.html")


def faq(request):
    return render(request, "pages/faq.html")
