import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from billing.models import Plan, Subscription
from members.models import MemberProfile

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(email="user@example.com", password="TestPass123!", **kwargs):
    username = kwargs.pop("username", email)
    user = User.objects.create_user(username=username, email=email, password=password, **kwargs)
    MemberProfile.objects.get_or_create(user=user)
    return user


def make_plan(name="free", **kwargs):
    defaults = {
        "max_projects": 1,
        "max_tasks_per_month": 10,
        "price_cents": 0,
    }
    defaults.update(kwargs)
    return Plan.objects.get_or_create(name=name, defaults=defaults)[0]


# ---------------------------------------------------------------------------
# Plan model
# ---------------------------------------------------------------------------

class PlanModelTests(TestCase):
    def test_str_representation(self):
        plan = make_plan(name="starter", price_cents=4900)
        self.assertEqual(str(plan), "Starter")

    def test_price_dollars(self):
        plan = make_plan(name="pro", price_cents=14900)
        self.assertAlmostEqual(plan.price_dollars, 149.0)

    def test_free_plan_price_dollars(self):
        plan = make_plan(name="free", price_cents=0)
        self.assertEqual(plan.price_dollars, 0.0)

    def test_ordering_by_price(self):
        make_plan(name="pro", price_cents=14900)
        make_plan(name="starter", price_cents=4900)
        make_plan(name="free", price_cents=0)
        plans = list(Plan.objects.all())
        prices = [p.price_cents for p in plans]
        self.assertEqual(prices, sorted(prices))


# ---------------------------------------------------------------------------
# Subscription model
# ---------------------------------------------------------------------------

class SubscriptionModelTests(TestCase):
    def test_str_representation(self):
        user = make_user(email="sub@example.com", username="subuser")
        plan = make_plan(name="starter", price_cents=4900)
        sub = Subscription.objects.create(user=user, plan=plan)
        self.assertIn("sub@example.com", str(sub))
        self.assertIn("Starter", str(sub))

    def test_default_status_is_active(self):
        user = make_user(email="active@example.com", username="activeuser")
        plan = make_plan()
        sub = Subscription.objects.create(user=user, plan=plan)
        self.assertEqual(sub.status, "active")


# ---------------------------------------------------------------------------
# GET /dashboard/billing/
# ---------------------------------------------------------------------------

class BillingPageViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/billing/"
        self.user = make_user()

    def test_requires_login(self):
        resp = self.client.get(self.url)
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_returns_200(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_context_contains_plan_features(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("plan_features", resp.context)
        self.assertGreater(len(resp.context["plan_features"]), 0)

    def test_context_contains_current_plan(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("current_plan", resp.context)
        self.assertIn("current_plan_name", resp.context)

    def test_context_contains_usage_info(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        for key in ("tasks_this_month", "max_tasks", "usage_pct"):
            self.assertIn(key, resp.context)

    def test_free_plan_created_when_no_subscription(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["current_plan_name"], "free")
        self.assertTrue(Plan.objects.filter(name="free").exists())

    def test_existing_subscription_shown(self):
        plan = make_plan(name="starter", price_cents=4900)
        Subscription.objects.create(user=self.user, plan=plan)

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["current_plan_name"], "starter")

    def test_session_id_param_shows_success_message(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url, {"session_id": "cs_test_abc123"})
        self.assertEqual(resp.status_code, 200)

    def test_context_contains_comparison_table(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertIn("comparison_table", resp.context)

    def test_usage_pct_capped_at_100(self):
        plan = make_plan(name="starter", max_tasks_per_month=1, price_cents=4900)
        Subscription.objects.create(user=self.user, plan=plan)

        from tasks.models import Task
        from projects.models import Project
        project = Project.objects.create(owner=self.user, name="P", github_repo="o/r")
        for _ in range(5):
            Task.objects.create(
                project=project,
                created_by=self.user,
                title="t",
                description="d",
            )

        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertLessEqual(resp.context["usage_pct"], 100)


# ---------------------------------------------------------------------------
# POST /dashboard/billing/checkout/
# ---------------------------------------------------------------------------

class CheckoutSessionViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/dashboard/billing/checkout/"
        self.user = make_user()

    def test_requires_login(self):
        resp = self.client.post(self.url, {"plan": "starter"})
        self.assertRedirects(resp, f"/login/?next={self.url}", fetch_redirect_response=False)

    def test_get_not_allowed(self):
        self.client.force_login(self.user)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 405)

    def test_invalid_plan_redirects_with_error(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"plan": "bogus"})
        self.assertRedirects(resp, "/dashboard/billing/", fetch_redirect_response=False)

    def test_plan_without_stripe_price_id_redirects(self):
        make_plan(name="starter", stripe_price_id="", price_cents=4900)
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"plan": "starter"})
        self.assertRedirects(resp, "/dashboard/billing/", fetch_redirect_response=False)

    def test_plan_not_in_db_redirects_with_error(self):
        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"plan": "pro"})
        self.assertRedirects(resp, "/dashboard/billing/", fetch_redirect_response=False)

    @patch("billing.views.stripe.checkout.Session.create")
    def test_valid_plan_redirects_to_stripe(self, mock_create):
        make_plan(name="starter", stripe_price_id="price_test_123", price_cents=4900)
        mock_session = MagicMock()
        mock_session.url = "https://checkout.stripe.com/pay/test"
        mock_create.return_value = mock_session

        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"plan": "starter"})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("stripe.com", resp["Location"])

    @patch("billing.views.stripe.checkout.Session.create")
    def test_stripe_error_redirects_with_message(self, mock_create):
        import stripe
        make_plan(name="starter", stripe_price_id="price_test_123", price_cents=4900)
        mock_create.side_effect = stripe.error.StripeError("Network error")

        self.client.force_login(self.user)
        resp = self.client.post(self.url, {"plan": "starter"})
        self.assertRedirects(resp, "/dashboard/billing/", fetch_redirect_response=False)


# ---------------------------------------------------------------------------
# POST /webhooks/stripe/
# ---------------------------------------------------------------------------

class StripeWebhookViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/webhooks/stripe/"

    def test_invalid_payload_returns_400(self):
        with patch("billing.views.stripe.Webhook.construct_event", side_effect=ValueError):
            resp = self.client.post(
                self.url,
                data="bad payload",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=abc",
            )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_signature_returns_400(self):
        import stripe
        with patch(
            "billing.views.stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError("bad sig", "sig_header"),
        ):
            resp = self.client.post(
                self.url,
                data=json.dumps({"type": "checkout.session.completed"}),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=bad",
            )
        self.assertEqual(resp.status_code, 400)

    def test_valid_event_returns_200(self):
        mock_event = {"type": "payment_intent.created", "data": {"object": {}}}
        with patch("billing.views.stripe.Webhook.construct_event", return_value=mock_event):
            resp = self.client.post(
                self.url,
                data=json.dumps(mock_event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
            )
        self.assertEqual(resp.status_code, 200)

    def test_checkout_completed_provisions_subscription(self):
        user = make_user(email="webhook@example.com", username="webhookuser")
        plan = make_plan(name="starter", price_cents=4900)

        session_obj = {
            "id": "cs_test_123",
            "metadata": {"user_id": str(user.pk), "plan_name": "starter"},
            "subscription": "sub_123",
        }
        mock_event = {"type": "checkout.session.completed", "data": {"object": session_obj}}

        with patch("billing.views.stripe.Webhook.construct_event", return_value=mock_event):
            resp = self.client.post(
                self.url,
                data=json.dumps(mock_event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
            )

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Subscription.objects.filter(user=user, plan=plan).exists())
        user.refresh_from_db()
        self.assertEqual(user.plan, "starter")

    def test_checkout_completed_missing_metadata_handled(self):
        session_obj = {"id": "cs_test_456", "metadata": {}, "subscription": ""}
        mock_event = {"type": "checkout.session.completed", "data": {"object": session_obj}}

        with patch("billing.views.stripe.Webhook.construct_event", return_value=mock_event):
            resp = self.client.post(
                self.url,
                data=json.dumps(mock_event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
            )
        self.assertEqual(resp.status_code, 200)

    def test_checkout_completed_unknown_user_handled(self):
        make_plan(name="starter", price_cents=4900)
        session_obj = {
            "id": "cs_test_789",
            "metadata": {"user_id": "99999", "plan_name": "starter"},
            "subscription": "sub_456",
        }
        mock_event = {"type": "checkout.session.completed", "data": {"object": session_obj}}

        with patch("billing.views.stripe.Webhook.construct_event", return_value=mock_event):
            resp = self.client.post(
                self.url,
                data=json.dumps(mock_event),
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="t=123,v1=valid",
            )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Subscription.objects.count(), 0)
