import logging

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from tasks.models import Task

from .models import Plan, Subscription

logger = logging.getLogger(__name__)

# ── Plan display metadata ──────────────────────────────────────────────────────
# Describes features shown on the billing page.  Limits (max_projects,
# max_tasks) are authoritative in the Plan DB model; these are for display only.
PLAN_FEATURES = [
    {
        "name": "free",
        "display_name": "Free",
        "price_display": "Free",
        "period": "",
        "description": "Get started with TARS at no cost.",
        "highlight": False,
        "features": [
            "1 project",
            "10 tasks / month",
            "Community support",
        ],
        "missing": [
            "Priority queue",
            "Dedicated worker",
            "Slack integration",
        ],
    },
    {
        "name": "starter",
        "display_name": "Starter",
        "price_display": "$49",
        "period": "/mo",
        "description": "For solo developers shipping at speed.",
        "highlight": True,
        "features": [
            "5 projects",
            "50 tasks / month",
            "Priority queue",
            "Email support",
        ],
        "missing": [
            "Dedicated worker",
            "Slack integration",
        ],
    },
    {
        "name": "pro",
        "display_name": "Pro",
        "price_display": "$149",
        "period": "/mo",
        "description": "Unlimited power for growing teams.",
        "highlight": False,
        "features": [
            "Unlimited projects",
            "Unlimited tasks",
            "Priority queue",
            "Dedicated worker",
            "Slack integration",
            "Priority support",
        ],
        "missing": [],
    },
    {
        "name": "enterprise",
        "display_name": "Enterprise",
        "price_display": "Custom",
        "period": "",
        "description": "Tailored SLAs and custom integrations.",
        "highlight": False,
        "features": [
            "Everything in Pro",
            "Custom task limits",
            "Custom worker allocation",
            "SLA guarantees",
            "Dedicated account manager",
            "Custom integrations",
        ],
        "missing": [],
    },
]

# Comparison table rows: (label, free, starter, pro, enterprise)
COMPARISON_TABLE = [
    ("Projects",           "1",         "5",           "Unlimited",  "Custom"),
    ("Tasks / month",      "10",        "50",          "Unlimited",  "Custom"),
    ("Priority queue",     False,       True,          True,         True),
    ("Dedicated worker",   False,       False,         True,         True),
    ("Slack integration",  False,       False,         True,         True),
    ("Support",            "Community", "Email",       "Priority",   "Dedicated"),
    ("SLA",                False,       False,         False,        True),
]


@login_required
def billing_page(request):
    # Resolve the user's active plan
    try:
        subscription = request.user.subscription
        current_plan = subscription.plan
        current_plan_name = current_plan.name
    except Subscription.DoesNotExist:
        subscription = None
        current_plan, _ = Plan.objects.get_or_create(
            name="free",
            defaults={
                "max_projects": 1,
                "max_tasks_per_month": 10,
                "price_cents": 0,
            },
        )
        current_plan_name = "free"

    # Usage meter — tasks submitted this calendar month
    now = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    tasks_this_month = Task.objects.filter(
        created_by=request.user, created_at__gte=month_start
    ).count()

    max_tasks = current_plan.max_tasks_per_month
    if max_tasks > 0:
        usage_pct = min(round(tasks_this_month / max_tasks * 100), 100)
    else:
        usage_pct = 0  # unlimited — no meter needed

    # Stripe checkout success redirect
    if request.GET.get("session_id"):
        messages.success(request, "Your subscription has been updated — welcome to the new plan!")

    ctx = {
        "subscription": subscription,
        "current_plan": current_plan,
        "current_plan_name": current_plan_name,
        "plan_features": PLAN_FEATURES,
        "comparison_table": COMPARISON_TABLE,
        "tasks_this_month": tasks_this_month,
        "max_tasks": max_tasks,
        "usage_pct": usage_pct,
        "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
    }
    return render(request, "billing/billing.html", ctx)


@login_required
@require_POST
def create_checkout_session(request):
    plan_name = request.POST.get("plan", "").strip()
    if plan_name not in ("starter", "pro"):
        messages.error(request, "Invalid plan selected.")
        return redirect("billing:billing")

    try:
        plan = Plan.objects.get(name=plan_name)
    except Plan.DoesNotExist:
        messages.error(request, "Plan not found. Please contact support.")
        return redirect("billing:billing")

    if not plan.stripe_price_id:
        messages.error(request, "This plan is not yet available for online purchase. Please contact us.")
        return redirect("billing:billing")

    stripe.api_key = settings.STRIPE_SECRET_KEY

    base_url = f"{request.scheme}://{request.get_host()}"
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=request.user.email,
            line_items=[{"price": plan.stripe_price_id, "quantity": 1}],
            success_url=f"{base_url}/dashboard/billing/?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base_url}/dashboard/billing/",
            metadata={
                "user_id": str(request.user.pk),
                "plan_name": plan_name,
            },
        )
    except stripe.error.StripeError as exc:
        logger.error("Stripe checkout error for user %s: %s", request.user.pk, exc)
        messages.error(request, "Could not connect to the payment processor. Please try again.")
        return redirect("billing:billing")

    return redirect(session.url, permanent=False)


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)

    if event["type"] == "checkout.session.completed":
        _handle_checkout_completed(event["data"]["object"])

    return HttpResponse(status=200)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _handle_checkout_completed(session):
    """Provision the subscription after a successful Stripe Checkout."""
    User = get_user_model()

    metadata = session.get("metadata") or {}
    user_id = metadata.get("user_id")
    plan_name = metadata.get("plan_name")

    if not user_id or not plan_name:
        logger.warning("stripe webhook: missing metadata on session %s", session.get("id"))
        return

    try:
        user = User.objects.get(pk=user_id)
        plan = Plan.objects.get(name=plan_name)
    except User.DoesNotExist:
        logger.error("stripe webhook: user %s not found", user_id)
        return
    except Plan.DoesNotExist:
        logger.error("stripe webhook: plan %r not found", plan_name)
        return

    stripe_subscription_id = session.get("subscription") or ""

    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": plan,
            "stripe_subscription_id": stripe_subscription_id,
            "status": "active",
        },
    )

    # Keep CustomUser.plan in sync
    user.plan = plan_name
    user.save(update_fields=["plan"])

    logger.info("stripe webhook: provisioned %s → %s", user.email, plan_name)
