from django.shortcuts import render, redirect
from .forms import InquiryForm


def get_started(request):
    if request.method == 'POST':
        form = InquiryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('inquiries:thank_you')
    else:
        form = InquiryForm()
    return render(request, 'inquiries/get_started.html', {'form': form})


def thank_you(request):
    return render(request, 'inquiries/thank_you.html')
