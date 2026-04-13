import json
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone

from projects.models import Project
from tasks.models import Task
from workers.models import TaskAssignment, Worker

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(**kwargs):
    defaults = {"username": "testuser", "password": "pass"}
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def make_project(owner, **kwargs):
    defaults = {
        "name": "Test Project",
        "github_repo": "owner/repo",
        "default_branch": "main",
    }
    defaults.update(kwargs)
    return Project.objects.create(owner=owner, **defaults)


def make_task(project, owner, **kwargs):
    defaults = {
        "title": "Test Task",
        "description": "Do something",
        "status": "pending",
        "priority": 50,
    }
    defaults.update(kwargs)
    return Task.objects.create(project=project, created_by=owner, **defaults)


def make_worker(**kwargs):
    defaults = {
        "hostname": "worker-1",
        "capacity": 2,
        "current_load": 0,
        "status": "online",
    }
    defaults.update(kwargs)
    return Worker.objects.create(**defaults)


# ---------------------------------------------------------------------------
# POST /api/workers/register/
# ---------------------------------------------------------------------------

class RegisterViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/api/workers/register/"

    def test_register_success(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({"hostname": "worker-1", "capacity": 4}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("worker_id", data)
        self.assertIn("api_key", data)
        self.assertEqual(Worker.objects.count(), 1)
        worker = Worker.objects.get()
        self.assertEqual(worker.hostname, "worker-1")
        self.assertEqual(worker.capacity, 4)
        self.assertEqual(worker.status, "online")

    def test_register_missing_hostname(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({"capacity": 1}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_register_invalid_json(self):
        resp = self.client.post(
            self.url,
            data="not-json",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_register_default_capacity(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({"hostname": "worker-x"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(Worker.objects.get().capacity, 1)


# ---------------------------------------------------------------------------
# POST /api/workers/heartbeat/
# ---------------------------------------------------------------------------

class HeartbeatViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/api/workers/heartbeat/"
        self.worker = make_worker()

    def _post(self, data=None):
        return self.client.post(
            self.url,
            data=json.dumps(data or {}),
            content_type="application/json",
            HTTP_X_WORKER_KEY=str(self.worker.api_key),
        )

    def test_heartbeat_updates_timestamp(self):
        before = timezone.now()
        resp = self._post()
        self.assertEqual(resp.status_code, 200)
        self.worker.refresh_from_db()
        self.assertGreaterEqual(self.worker.last_heartbeat, before)

    def test_heartbeat_updates_load_and_status(self):
        resp = self._post({"current_load": 1, "status": "busy"})
        self.assertEqual(resp.status_code, 200)
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.current_load, 1)
        self.assertEqual(self.worker.status, "busy")

    def test_heartbeat_invalid_key(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_X_WORKER_KEY="00000000-0000-0000-0000-000000000000",
        )
        self.assertEqual(resp.status_code, 401)

    def test_heartbeat_missing_key(self):
        resp = self.client.post(self.url, data=json.dumps({}), content_type="application/json")
        self.assertEqual(resp.status_code, 401)


# ---------------------------------------------------------------------------
# GET /api/workers/next-task/
# ---------------------------------------------------------------------------

class NextTaskViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/api/workers/next-task/"
        self.user = make_user()
        self.project = make_project(self.user)
        self.worker = make_worker(hostname="worker-1", capacity=2, current_load=0)

    def _get(self, worker=None):
        w = worker or self.worker
        return self.client.get(
            self.url,
            HTTP_X_WORKER_KEY=str(w.api_key),
        )

    def test_no_pending_tasks_returns_null(self):
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["task"])

    def test_assigns_pending_task(self):
        task = make_task(self.project, self.user)
        resp = self._get()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNotNone(data["task"])
        self.assertEqual(data["task"]["id"], task.pk)
        task.refresh_from_db()
        self.assertEqual(task.status, "assigned")
        self.assertEqual(TaskAssignment.objects.count(), 1)

    def test_worker_at_max_load_returns_null(self):
        make_task(self.project, self.user)
        self.worker.current_load = 2
        self.worker.save()
        resp = self._get()
        self.assertIsNone(resp.json()["task"])

    def test_higher_priority_task_picked_first(self):
        low = make_task(self.project, self.user, title="Low", priority=10)
        project2 = make_project(self.user, name="P2", github_repo="owner/repo2")
        high = make_task(project2, self.user, title="High", priority=90)
        resp = self._get()
        self.assertEqual(resp.json()["task"]["id"], high.pk)

    def test_age_bonus_applied(self):
        # Create two tasks on different projects; the older low-priority one
        # should beat the newer high-priority one once the age bonus kicks in.
        project2 = make_project(self.user, name="P2", github_repo="owner/repo2")
        old_task = make_task(self.project, self.user, title="Old", priority=10)
        # Backdate created_at by 60 minutes → age bonus = 50 (capped)
        Task.objects.filter(pk=old_task.pk).update(
            created_at=timezone.now() - timedelta(minutes=60)
        )
        old_task.refresh_from_db()

        new_task = make_task(project2, self.user, title="New", priority=55)

        # old_task effective score = 10 + 50 = 60, new_task = 55 + ~0 = 55
        resp = self._get()
        self.assertEqual(resp.json()["task"]["id"], old_task.pk)

    def test_cache_warm_bonus_applied(self):
        project2 = make_project(self.user, name="P2", github_repo="owner/repo2")
        task1 = make_task(self.project, self.user, title="Warm", priority=50)
        task2 = make_task(project2, self.user, title="Cold", priority=55)

        # Record a recent assignment for this worker on project1
        dummy_task = make_task(self.project, self.user, title="Dummy", status="completed")
        TaskAssignment.objects.create(task=dummy_task, worker=self.worker)

        # task1 score = 50 + ~0 + 10 (cache warm) = 60 > task2 score = 55
        resp = self._get()
        self.assertEqual(resp.json()["task"]["id"], task1.pk)

    def test_busy_project_excluded(self):
        # task1 on project (which has an active task) should be skipped
        make_task(self.project, self.user, title="Active", status="in_progress")
        make_task(self.project, self.user, title="Pending")  # same project → excluded

        project2 = make_project(self.user, name="P2", github_repo="owner/repo2")
        free_task = make_task(project2, self.user, title="Free")

        resp = self._get()
        self.assertEqual(resp.json()["task"]["id"], free_task.pk)

    def test_task_assignment_record_created(self):
        make_task(self.project, self.user)
        self._get()
        self.assertEqual(TaskAssignment.objects.count(), 1)
        a = TaskAssignment.objects.get()
        self.assertEqual(a.worker, self.worker)
        self.assertIsNone(a.result)

    def test_invalid_key_rejected(self):
        resp = self.client.get(self.url, HTTP_X_WORKER_KEY="bad-key")
        self.assertEqual(resp.status_code, 401)


# ---------------------------------------------------------------------------
# POST /api/workers/task/<id>/update/
# ---------------------------------------------------------------------------

class TaskUpdateViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = make_user()
        self.project = make_project(self.user)
        self.worker = make_worker()
        self.task = make_task(self.project, self.user, status="assigned")
        self.assignment = TaskAssignment.objects.create(task=self.task, worker=self.worker)

    def _post(self, task_id, data, worker=None):
        w = worker or self.worker
        return self.client.post(
            f"/api/workers/task/{task_id}/update/",
            data=json.dumps(data),
            content_type="application/json",
            HTTP_X_WORKER_KEY=str(w.api_key),
        )

    def test_status_update(self):
        resp = self._post(self.task.pk, {"status": "in_progress"})
        self.assertEqual(resp.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "in_progress")

    def test_in_progress_sets_started_at(self):
        self._post(self.task.pk, {"status": "in_progress"})
        self.task.refresh_from_db()
        self.assertIsNotNone(self.task.started_at)

    def test_completed_updates_assignment_success(self):
        self._post(self.task.pk, {"status": "completed"})
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.result, "success")
        self.assertIsNotNone(self.assignment.completed_at)

    def test_failed_updates_assignment_failed(self):
        self._post(self.task.pk, {"status": "failed"})
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.result, "failed")

    def test_branch_and_pr_url_update(self):
        self._post(self.task.pk, {"branch_name": "feat/foo", "pr_url": "https://github.com/pr/1"})
        self.task.refresh_from_db()
        self.assertEqual(self.task.branch_name, "feat/foo")
        self.assertEqual(self.task.pr_url, "https://github.com/pr/1")

    def test_task_not_found(self):
        resp = self._post(99999, {"status": "in_progress"})
        self.assertEqual(resp.status_code, 404)

    def test_invalid_key_rejected(self):
        resp = self.client.post(
            f"/api/workers/task/{self.task.pk}/update/",
            data=json.dumps({"status": "in_progress"}),
            content_type="application/json",
            HTTP_X_WORKER_KEY="bad",
        )
        self.assertEqual(resp.status_code, 401)


# ---------------------------------------------------------------------------
# check_stuck_tasks management command
# ---------------------------------------------------------------------------

class CheckStuckTasksCommandTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.project = make_project(self.user)

    def _make_stale_worker(self):
        worker = make_worker(hostname="stale-worker")
        Worker.objects.filter(pk=worker.pk).update(
            last_heartbeat=timezone.now() - timedelta(minutes=10)
        )
        worker.refresh_from_db()
        return worker

    def test_stuck_task_requeued(self):
        worker = self._make_stale_worker()
        task = make_task(self.project, self.user, status="assigned")
        assignment = TaskAssignment.objects.create(task=task, worker=worker)
        # Backdate assignment beyond the 30-minute threshold
        TaskAssignment.objects.filter(pk=assignment.pk).update(
            assigned_at=timezone.now() - timedelta(minutes=35)
        )

        call_command("check_stuck_tasks", verbosity=0)

        task.refresh_from_db()
        self.assertEqual(task.status, "pending")
        self.assertIsNone(task.worker_id)

        assignment.refresh_from_db()
        self.assertEqual(assignment.result, "timeout")
        self.assertIsNotNone(assignment.completed_at)

    def test_recent_assignment_not_requeued(self):
        worker = self._make_stale_worker()
        task = make_task(self.project, self.user, status="assigned")
        # Assignment is recent (5 min ago) — should not be touched
        TaskAssignment.objects.create(task=task, worker=worker)

        call_command("check_stuck_tasks", verbosity=0)

        task.refresh_from_db()
        self.assertEqual(task.status, "assigned")

    def test_active_worker_not_requeued(self):
        # Worker with a recent heartbeat — task should stay assigned
        worker = make_worker(hostname="active-worker")
        Worker.objects.filter(pk=worker.pk).update(last_heartbeat=timezone.now())
        task = make_task(self.project, self.user, status="assigned")
        assignment = TaskAssignment.objects.create(task=task, worker=worker)
        TaskAssignment.objects.filter(pk=assignment.pk).update(
            assigned_at=timezone.now() - timedelta(minutes=35)
        )

        call_command("check_stuck_tasks", verbosity=0)

        task.refresh_from_db()
        self.assertEqual(task.status, "assigned")

    def test_completed_assignment_not_requeued(self):
        worker = self._make_stale_worker()
        task = make_task(self.project, self.user, status="completed")
        assignment = TaskAssignment.objects.create(
            task=task, worker=worker, result="success", completed_at=timezone.now()
        )
        TaskAssignment.objects.filter(pk=assignment.pk).update(
            assigned_at=timezone.now() - timedelta(minutes=35)
        )

        call_command("check_stuck_tasks", verbosity=0)

        task.refresh_from_db()
        self.assertEqual(task.status, "completed")


# ---------------------------------------------------------------------------
# Worker list admin dashboard
# ---------------------------------------------------------------------------

class WorkerListViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = "/admin-dashboard/workers/"
        self.staff = make_user(username="admin", is_staff=True)
        self.client.force_login(self.staff)

    def test_requires_staff(self):
        non_staff = make_user(username="regular")
        self.client.force_login(non_staff)
        resp = self.client.get(self.url)
        self.assertNotEqual(resp.status_code, 200)

    def test_renders_for_staff(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)

    def test_stale_workers_marked_offline(self):
        worker = make_worker(hostname="stale", status="online")
        Worker.objects.filter(pk=worker.pk).update(
            last_heartbeat=timezone.now() - timedelta(minutes=10)
        )
        self.client.get(self.url)
        worker.refresh_from_db()
        self.assertEqual(worker.status, "offline")

    def test_context_contains_stats(self):
        resp = self.client.get(self.url)
        for key in ("pending_count", "active_count", "stuck_count", "total_assignments", "success_rate"):
            self.assertIn(key, resp.context)

    def test_success_rate_calculation(self):
        user = make_user(username="proj_owner")
        project = make_project(user)
        worker = make_worker()
        task1 = make_task(project, user, status="completed")
        task2 = make_task(project, user, status="failed")
        TaskAssignment.objects.create(task=task1, worker=worker, result="success", completed_at=timezone.now())
        TaskAssignment.objects.create(task=task2, worker=worker, result="failed", completed_at=timezone.now())

        resp = self.client.get(self.url)
        self.assertEqual(resp.context["success_rate"], 50)

    def test_recent_assignments_in_context(self):
        user = make_user(username="proj_owner2")
        project = make_project(user, github_repo="owner/repo3")
        worker = make_worker(hostname="w2")
        task = make_task(project, user)
        TaskAssignment.objects.create(task=task, worker=worker)

        resp = self.client.get(self.url)
        self.assertIn("recent_assignments", resp.context)
        self.assertEqual(len(resp.context["recent_assignments"]), 1)
