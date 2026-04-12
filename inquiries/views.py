import json

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Count
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Inquiry


def _add_cors_headers(response):
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


@csrf_exempt
@require_http_methods(['POST', 'OPTIONS'])
def submit_inquiry(request):
    if request.method == 'OPTIONS':
        return _add_cors_headers(JsonResponse({}))

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return _add_cors_headers(JsonResponse({'error': 'Invalid JSON'}, status=400))

    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    message = data.get('message', '').strip()

    errors = {}
    if not name:
        errors['name'] = 'This field is required.'
    if not email:
        errors['email'] = 'This field is required.'
    else:
        try:
            validate_email(email)
        except ValidationError:
            errors['email'] = 'Enter a valid email address.'
    if not message:
        errors['message'] = 'This field is required.'

    if errors:
        return _add_cors_headers(JsonResponse({'errors': errors}, status=400))

    inquiry = Inquiry.objects.create(name=name, email=email, message=message)
    return _add_cors_headers(JsonResponse({
        'id': inquiry.pk,
        'status': inquiry.status,
        'message': 'Inquiry submitted successfully.',
    }, status=201))


@require_http_methods(['GET'])
def inquiry_stats(request):
    api_key = request.headers.get('X-Api-Key', '')
    expected = getattr(settings, 'TARS_API_KEY', '')

    if not expected or api_key != expected:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    counts = dict(
        Inquiry.objects.values('status').annotate(count=Count('id')).values_list('status', 'count')
    )
    stats = {status: counts.get(status, 0) for status, _ in Inquiry.STATUS_CHOICES}
    return JsonResponse({'stats': stats})
