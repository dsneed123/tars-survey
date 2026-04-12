import json

from django.conf import settings
from django.db.models import Count
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Inquiry

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
}


def _cors_json_response(data, status=200):
    response = JsonResponse(data, status=status)
    for key, value in _CORS_HEADERS.items():
        response[key] = value
    return response


@csrf_exempt
def submit_inquiry(request):
    if request.method == "OPTIONS":
        response = JsonResponse({})
        for key, value in _CORS_HEADERS.items():
            response[key] = value
        return response

    if request.method != "POST":
        return _cors_json_response({"error": "Method not allowed"}, status=405)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _cors_json_response({"error": "Invalid JSON body"}, status=400)

    if not isinstance(data, dict):
        return _cors_json_response({"error": "Request body must be a JSON object"}, status=400)

    required_fields = ["name", "email", "company", "team_size", "use_case"]
    missing = [f for f in required_fields if not str(data.get(f, "")).strip()]
    if missing:
        return _cors_json_response(
            {"error": "Missing required fields", "fields": missing},
            status=400,
        )

    email = str(data["email"]).strip()
    at_index = email.find("@")
    if at_index < 1 or "." not in email[at_index + 1:]:
        return _cors_json_response({"error": "Invalid email address"}, status=400)

    inquiry = Inquiry.objects.create(
        name=str(data["name"]).strip(),
        email=email,
        company=str(data["company"]).strip(),
        github_repo=str(data.get("github_repo", "")).strip(),
        team_size=str(data["team_size"]).strip(),
        use_case=str(data["use_case"]).strip(),
    )

    return _cors_json_response(
        {
            "success": True,
            "id": inquiry.id,
            "message": "Inquiry submitted successfully",
        },
        status=201,
    )


def inquiry_stats(request):
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    api_key = request.headers.get("X-Api-Key", "")
    expected_key = getattr(settings, "TARS_API_KEY", "")

    if not expected_key or api_key != expected_key:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    counts = dict(
        Inquiry.objects.values("status")
        .annotate(count=Count("id"))
        .values_list("status", "count")
    )

    stats = {status: counts.get(status, 0) for status, _ in Inquiry.STATUS_CHOICES}
    stats["total"] = sum(stats.values())

    return JsonResponse({"stats": stats})
