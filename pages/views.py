from django.shortcuts import render


def about(request):
    return render(request, 'pages/about.html')


def faq(request):
    return render(request, 'pages/faq.html')
