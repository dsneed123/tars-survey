import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from . import controller
from .models import Conversation, Message


def _body(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return {}


@login_required
def chat_home(request):
    """Full-screen model-chat UI. Separate from projects/tasks."""
    conversations = Conversation.objects.filter(user=request.user)
    return render(request, "chat/chat.html", {"conversations": conversations})


@login_required
@require_GET
def conversation_detail(request, pk):
    convo = get_object_or_404(Conversation, pk=pk, user=request.user)
    return JsonResponse({
        "id": convo.pk,
        "title": convo.title,
        "model": convo.model,
        "messages": [{"role": m.role, "content": m.content} for m in convo.messages.all()],
    })


@login_required
@require_POST
def send(request):
    """Append a user message, get a model reply via the controller, persist both."""
    data = _body(request)
    message = (data.get("message") or "").strip()
    if not message:
        return JsonResponse({"error": "Message is required"}, status=400)
    model = (data.get("model") or "").strip()
    cid = data.get("conversation_id")

    if cid:
        convo = get_object_or_404(Conversation, pk=cid, user=request.user)
    else:
        convo = Conversation.objects.create(
            user=request.user, title=message[:60], model=model
        )

    Message.objects.create(conversation=convo, role="user", content=message)
    history = [{"role": m.role, "content": m.content} for m in convo.messages.all()]

    try:
        reply = controller.generate_reply(history, model or convo.model or None)
    except controller.ControllerError as e:
        return JsonResponse({"error": str(e)}, status=502)

    Message.objects.create(conversation=convo, role="assistant", content=reply)
    if model:
        convo.model = model
    convo.save()  # bumps updated_at
    return JsonResponse({
        "conversation_id": convo.pk,
        "title": convo.title,
        "reply": reply,
    })


@login_required
@require_POST
def clear_conversation(request, pk):
    """Clear (delete) a single conversation."""
    convo = get_object_or_404(Conversation, pk=pk, user=request.user)
    convo.delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def clear_all(request):
    """Clear ALL of the user's conversations."""
    Conversation.objects.filter(user=request.user).delete()
    return JsonResponse({"ok": True})


@login_required
@require_GET
def models(request):
    """Proxy: available models + which are loaded."""
    try:
        return JsonResponse(controller.list_models())
    except controller.ControllerError as e:
        return JsonResponse({"models": [], "loaded": [], "error": str(e)})


@login_required
@require_POST
def model_load(request):
    """Spin a model up."""
    model = (_body(request).get("model") or "").strip()
    if not model:
        return JsonResponse({"error": "model is required"}, status=400)
    try:
        controller.load_model(model)
    except controller.ControllerError as e:
        return JsonResponse({"error": str(e)}, status=502)
    return JsonResponse({"ok": True, "loaded": model})


@login_required
@require_POST
def model_unload(request):
    """Spin a model down."""
    model = (_body(request).get("model") or "").strip()
    if not model:
        return JsonResponse({"error": "model is required"}, status=400)
    try:
        controller.unload_model(model)
    except controller.ControllerError as e:
        return JsonResponse({"error": str(e)}, status=502)
    return JsonResponse({"ok": True, "unloaded": model})
