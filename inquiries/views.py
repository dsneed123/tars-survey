from django.shortcuts import render, redirect
from .forms import InquiryForm


def inquiry_form(request):
    if request.method == 'POST':
        form = InquiryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('inquiries:success')
    else:
        form = InquiryForm()
    return render(request, 'inquiries/inquiry_form.html', {'form': form})


def inquiry_success(request):
    return render(request, 'inquiries/inquiry_success.html')
