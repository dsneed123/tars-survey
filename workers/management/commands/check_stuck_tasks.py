from django.core.management.base import BaseCommand
from django.utils import timezone

from tasks.models import Task
from workers.models import TaskAssignment

# A task is considered stuck if its assignment is older than this (minutes)
_STUCK_THRESHOLD_MINUTES = 30
# A worker's heartbeat is considered stale after this long (minutes)
_HEARTBEAT_STALE_MINUTES = 5


class Command(BaseCommand):
    help = (
        "Find tasks that have been assigned for more than 30 minutes with no "
        "worker heartbeat and requeue them as pending."
    )

    def handle(self, *args, **options):
        now = timezone.now()
        stuck_cutoff = now - timezone.timedelta(minutes=_STUCK_THRESHOLD_MINUTES)
        heartbeat_cutoff = now - timezone.timedelta(minutes=_HEARTBEAT_STALE_MINUTES)

        # Assignments that are older than the threshold and not yet resolved
        stuck_assignments = TaskAssignment.objects.filter(
            assigned_at__lt=stuck_cutoff,
            result__isnull=True,
            task__status__in=["assigned", "in_progress"],
            worker__last_heartbeat__lt=heartbeat_cutoff,
        ).select_related("task", "worker")

        requeued = 0
        for assignment in stuck_assignments:
            task = assignment.task

            self.stdout.write(
                f"Requeueing stuck task {task.pk} '{task.title}' "
                f"(assigned to {assignment.worker.hostname} at {assignment.assigned_at})"
            )

            # Mark the assignment as timed out
            assignment.result = "timeout"
            assignment.completed_at = now
            assignment.save(update_fields=["result", "completed_at"])

            # Reset the task back to pending
            task.status = "pending"
            task.worker_id = None
            task.save(update_fields=["status", "worker_id"])

            requeued += 1

        if requeued:
            self.stdout.write(
                self.style.SUCCESS(f"Requeued {requeued} stuck task(s).")
            )
        else:
            self.stdout.write("No stuck tasks found.")
