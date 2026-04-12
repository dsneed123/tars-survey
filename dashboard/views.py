from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Avg, F, ExpressionWrapper, DurationField
from datetime import timedelta
from inquiries.models import Inquiry, InquiryNote

STATUS_COLORS = {
    'new': 'primary',
    'contacted': 'info',
    'qualified': 'warning',
    'proposal': 'secondary',
    'won': 'success',
    'lost': 'danger',
}


@login_required
def dashboard_home(request):
    one_week_ago = timezone.now() - timedelta(days=7)

    total = Inquiry.objects.count()
    new_this_week = Inquiry.objects.filter(created_at__gte=one_week_ago).count()

    won = Inquiry.objects.filter(status=Inquiry.STATUS_WON).count()
    lost = Inquiry.objects.filter(status=Inquiry.STATUS_LOST).count()
    conversion_rate = round(won / (won + lost) * 100) if (won + lost) > 0 else 0

    avg_response = Inquiry.objects.filter(contacted_at__isnull=False).annotate(
        response_time=ExpressionWrapper(
            F('contacted_at') - F('created_at'),
            output_field=DurationField(),
        )
    ).aggregate(avg=Avg('response_time'))['avg']

    if avg_response:
        avg_hours = round(avg_response.total_seconds() / 3600, 1)
        avg_response_display = f"{avg_hours}h"
    else:
        avg_response_display = "N/A"

    pipeline = []
    for status, label in Inquiry.STATUS_CHOICES:
        inquiries = Inquiry.objects.filter(status=status).order_by('-created_at')
        pipeline.append({
            'status': status,
            'label': label,
            'color': STATUS_COLORS[status],
            'inquiries': inquiries,
            'count': inquiries.count(),
        })

    context = {
        'total': total,
        'new_this_week': new_this_week,
        'conversion_rate': conversion_rate,
        'avg_response_display': avg_response_display,
        'pipeline': pipeline,
    }
    return render(request, 'dashboard/dashboard.html', context)


@login_required
def inquiry_detail(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    notes = inquiry.notes.order_by('-created_at')
    context = {
        'inquiry': inquiry,
        'notes': notes,
        'statuses': Inquiry.STATUS_CHOICES,
        'status_color': STATUS_COLORS.get(inquiry.status, 'secondary'),
    }
    return render(request, 'dashboard/inquiry_detail.html', context)


@login_required
def add_note(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    if request.method == 'POST':
        note_text = request.POST.get('note', '').strip()
        if note_text:
            InquiryNote.objects.create(inquiry=inquiry, note=note_text)
    return redirect('dashboard:inquiry_detail', pk=pk)


@login_required
def change_status(request, pk):
    inquiry = get_object_or_404(Inquiry, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        valid_statuses = [s[0] for s in Inquiry.STATUS_CHOICES]
        if new_status in valid_statuses:
            if new_status == Inquiry.STATUS_CONTACTED and not inquiry.contacted_at:
                inquiry.contacted_at = timezone.now()
            inquiry.status = new_status
            inquiry.save()
    return redirect('dashboard:inquiry_detail', pk=pk)
