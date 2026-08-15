from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Dependency, DependencyType, Job, JobState, Layer, Task, TaskState

# ── Helpers ────────────────────────────────────────────────────────────────────


def _satisfy_dependency(dep):
    """Mark a single Dependency as satisfied and unblock the dependent task.

    Decrements depend_count on the dep_task (if present) and transitions the
    task to READY when all its blocking dependencies are resolved.  Also
    decrements the depend_tasks counter on the parent Job and Layer when the
    task is unblocked.
    """
    dep.is_satisfied = True
    dep.satisfied_at = timezone.now()
    dep.save()  # triggers dependency_pre_save which handles depend_count / depend_tasks


def _unblock_tasks_for_deps(dep_qs):
    """Satisfy a queryset of Dependency rows and unblock their dependent tasks.

    Called when a parent task, layer, or job completes.

    - **TASK_ON_TASK**: Fully handled by ``dependency_pre_save`` signal.  We call
      ``dep.save()`` directly (without pre-updating the DB) so the signal can see
      the old ``is_satisfied=False`` value and correctly decrement ``depend_count``.
    - **LAYER_ON_LAYER** / **JOB_ON_JOB**: No ``dep_task`` exists, so signals are
      useless here.  We bulk-update ``is_satisfied`` in the DB first, then
      directly walk the blocked layer/job's tasks to repair counters.
    """
    for dep in dep_qs.select_related("dep_task", "dep_layer", "dep_job"):
        if dep.type == DependencyType.TASK_ON_TASK:
            # Signal-driven path: do NOT pre-update the DB — let dep.save()
            # trigger dependency_pre_save which reads old is_satisfied=False.
            dep.is_satisfied = True
            dep.satisfied_at = timezone.now()
            dep.save()  # triggers dependency_pre_save → decrements dep_task.depend_count

        elif dep.type == DependencyType.LAYER_ON_LAYER and dep.dep_layer_id:
            # Bulk-mark satisfied first, then directly unblock the tasks
            Dependency.objects.filter(pk=dep.pk).update(
                is_satisfied=True,
                satisfied_at=timezone.now(),
            )
            _decrement_tasks_in_layer(dep.dep_layer_id)

        elif dep.type == DependencyType.JOB_ON_JOB and dep.dep_job_id:
            # Bulk-mark satisfied first, then directly unblock the tasks
            Dependency.objects.filter(pk=dep.pk).update(
                is_satisfied=True,
                satisfied_at=timezone.now(),
            )
            _decrement_tasks_in_job(dep.dep_job_id)



def _decrement_tasks_in_layer(layer_id):
    """Decrement depend_count for all WAITING tasks in a layer and unblock them.

    Used when a LAYER_ON_LAYER dependency is satisfied — the blocked layer's
    tasks should all have their depend_count decremented.  If any task's count
    reaches 0 it transitions to READY.
    """
    from .models import Job, Layer, Task, TaskState

    with transaction.atomic():
        tasks = list(Task.objects.select_for_update().filter(
            layer_id=layer_id, depend_count__gt=0
        ))
        unblocked_count = 0
        for task in tasks:
            task.depend_count -= 1
            if task.depend_count == 0 and task.state == TaskState.WAITING:
                task.state = TaskState.READY
                unblocked_count += 1
            task.save(update_fields=["depend_count", "state", "updated_at"])

        if unblocked_count > 0:
            Layer.objects.filter(id=layer_id).update(
                depend_tasks=F("depend_tasks") - unblocked_count,
                waiting_tasks=F("waiting_tasks") - unblocked_count,
                ready_tasks=F("ready_tasks") + unblocked_count,
            )
            first_task = Task.objects.filter(layer_id=layer_id).values("job_id").first()
            if first_task:
                Job.objects.filter(id=first_task["job_id"]).update(
                    depend_tasks=F("depend_tasks") - unblocked_count,
                    waiting_tasks=F("waiting_tasks") - unblocked_count,
                    ready_tasks=F("ready_tasks") + unblocked_count,
                )


def _decrement_tasks_in_job(job_id):
    """Decrement depend_count for all WAITING tasks in a job and unblock them.

    Used when a JOB_ON_JOB dependency is satisfied.
    """
    from .models import Job, Layer, Task, TaskState

    with transaction.atomic():
        tasks = list(Task.objects.select_for_update().filter(
            job_id=job_id, depend_count__gt=0
        ))
        layer_unblocked: dict[str, int] = {}
        for task in tasks:
            task.depend_count -= 1
            if task.depend_count == 0 and task.state == TaskState.WAITING:
                task.state = TaskState.READY
                lid = str(task.layer_id)
                layer_unblocked[lid] = layer_unblocked.get(lid, 0) + 1
            task.save(update_fields=["depend_count", "state", "updated_at"])

        total_unblocked = sum(layer_unblocked.values())
        if total_unblocked > 0:
            for lid, count in layer_unblocked.items():
                Layer.objects.filter(id=lid).update(
                    depend_tasks=F("depend_tasks") - count,
                    waiting_tasks=F("waiting_tasks") - count,
                    ready_tasks=F("ready_tasks") + count,
                )
            Job.objects.filter(id=job_id).update(
                depend_tasks=F("depend_tasks") - total_unblocked,
                waiting_tasks=F("waiting_tasks") - total_unblocked,
                ready_tasks=F("ready_tasks") + total_unblocked,
            )


def _satisfy_dependency(dep):
    """Mark a single TASK_ON_TASK Dependency as satisfied via signal path."""
    dep.is_satisfied = True
    dep.satisfied_at = timezone.now()
    dep.save()  # triggers dependency_pre_save which handles depend_count / depend_tasks


# ── Dependency signals ─────────────────────────────────────────────────────────



@receiver(post_save, sender=Dependency)
def dependency_post_save(sender, instance, created, **kwargs):
    """Handle dependency creation.

    When a new (unsatisfied) Dependency is created for a task:
    - Increments depend_count on the blocked task.
    - Increments depend_tasks on the parent Job and Layer.
    """
    if created and not instance.is_satisfied:
        if instance.dep_task_id:
            Task.objects.filter(id=instance.dep_task_id).update(depend_count=F("depend_count") + 1)
            # Also update depend_tasks on Job and Layer
            task = Task.objects.filter(id=instance.dep_task_id).values("job_id", "layer_id").first()
            if task:
                Layer.objects.filter(id=task["layer_id"]).update(depend_tasks=F("depend_tasks") + 1)
                Job.objects.filter(id=task["job_id"]).update(depend_tasks=F("depend_tasks") + 1)


@receiver(pre_save, sender=Dependency)
def dependency_pre_save(sender, instance, **kwargs):
    """Handle dependency satisfaction transitions.

    When a Dependency transitions from unsatisfied → satisfied:
    - Decrements depend_count on the blocked task.
    - If depend_count reaches 0 and the task is WAITING, transitions it to READY.
    - Decrements depend_tasks on the parent Job and Layer.
    """
    if instance.id:
        try:
            old_instance = Dependency.objects.get(id=instance.id)
            if not old_instance.is_satisfied and instance.is_satisfied:
                if instance.dep_task_id:
                    with transaction.atomic():
                        # Lock the row while evaluating
                        task = Task.objects.select_for_update().get(id=instance.dep_task_id)
                        task.depend_count -= 1
                        if task.depend_count == 0 and task.state == TaskState.WAITING:
                            task.state = TaskState.READY
                            # Decrement depend_tasks on Job and Layer when task is unblocked
                            Layer.objects.filter(id=task.layer_id).update(depend_tasks=F("depend_tasks") - 1)
                            Job.objects.filter(id=task.job_id).update(depend_tasks=F("depend_tasks") - 1)
                        task.save(update_fields=["depend_count", "state", "updated_at"])
        except Dependency.DoesNotExist:
            pass


@receiver(pre_delete, sender=Dependency)
def dependency_pre_delete(sender, instance, **kwargs):
    """Repair depend_count before a dependency is destroyed.

    Must be pre_delete so the dep_task_id is still available before CASCADE.
    Also decrements depend_tasks on Job and Layer if the task was still blocked.
    """
    if not instance.is_satisfied and instance.dep_task_id:
        with transaction.atomic():
            try:
                task = Task.objects.select_for_update().get(id=instance.dep_task_id)
                task.depend_count -= 1
                if task.depend_count == 0 and task.state == TaskState.WAITING:
                    task.state = TaskState.READY
                    # Task is no longer blocked — decrement depend_tasks
                    Layer.objects.filter(id=task.layer_id).update(depend_tasks=F("depend_tasks") - 1)
                    Job.objects.filter(id=task.job_id).update(depend_tasks=F("depend_tasks") - 1)
                task.save(update_fields=["depend_count", "state", "updated_at"])
            except Task.DoesNotExist:
                pass


# ── Task signals ───────────────────────────────────────────────────────────────


@receiver(pre_save, sender=Task)
def task_pre_save(sender, instance, update_fields=None, **kwargs):
    """Handle Task state transitions.

    1. Update parent Job and Layer counter caches.
    2. If task SUCCEEDED or SKIPPED: satisfy all TASK_ON_TASK dependencies
       blocking on this task.
    """
    # Fast-exit: if update_fields is specified and "state" is not in it, there
    # is no state transition to process. Skips the DB round-trip for saves that
    # only touch depend_count, checkpoint_count, or other non-state fields.
    if update_fields is not None and "state" not in update_fields:
        return

    try:
        old_instance = Task.objects.get(id=instance.id)
    except Task.DoesNotExist:
        # NOTE: In the standard job submission flow, tasks are created via
        # Task.objects.bulk_create(), which bypasses signals entirely. The
        # counter updates for that path are handled manually in services.py.
        # This block only fires when a Task is created via .create() or a
        # direct .save() call (e.g., from TaskFactory in tests or a management
        # command). Do NOT also update counters elsewhere for that code path.
        state_field = (
            "running_tasks" if instance.state == TaskState.CHECKPOINT else f"{instance.state.lower()}_tasks"
        )
        Layer.objects.filter(id=instance.layer_id).update(
            **{state_field: F(state_field) + 1},
            total_tasks=F("total_tasks") + 1,
        )
        Job.objects.filter(id=instance.job_id).update(
            **{state_field: F(state_field) + 1},
            total_tasks=F("total_tasks") + 1,
        )
        return

    if old_instance.state != instance.state:
        # State changed. Update parent counters atomically using F() expressions
        old_state_field = (
            "running_tasks" if old_instance.state == TaskState.CHECKPOINT else f"{old_instance.state.lower()}_tasks"
        )
        new_state_field = (
            "running_tasks" if instance.state == TaskState.CHECKPOINT else f"{instance.state.lower()}_tasks"
        )

        if old_state_field != new_state_field:
            Layer.objects.filter(id=instance.layer_id).update(
                **{old_state_field: F(old_state_field) - 1, new_state_field: F(new_state_field) + 1}
            )
            Job.objects.filter(id=instance.job_id).update(
                **{old_state_field: F(old_state_field) - 1, new_state_field: F(new_state_field) + 1}
            )

        # If transitioning to SUCCEEDED or SKIPPED, satisfy TASK_ON_TASK deps
        if instance.state in (TaskState.SUCCEEDED, TaskState.SKIPPED):
            # Record stop time
            instance.stopped_at = timezone.now()

            # Find and satisfy TASK_ON_TASK dependencies waiting on this task
            deps = Dependency.objects.filter(
                type=DependencyType.TASK_ON_TASK,
                parent_task_id=instance.id,
                is_satisfied=False,
            )
            _unblock_tasks_for_deps(deps)

        # Atomic state transitions for Job and Layer based on the newly updated counts
        if instance.state in (TaskState.RUNNING, TaskState.CHECKPOINT):
            Job.objects.filter(id=instance.job_id, is_paused=False).exclude(state=JobState.RUNNING).update(
                state=JobState.RUNNING
            )
            Layer.objects.filter(id=instance.layer_id).exclude(state=JobState.RUNNING).update(state=JobState.RUNNING)

        elif instance.state in (TaskState.SUCCEEDED, TaskState.SKIPPED, TaskState.FAILED):
            now = timezone.now()

            # Check if finished (all tasks are succeeded or skipped)
            finished_jobs = Job.objects.filter(
                id=instance.job_id,
                total_tasks__gt=0,
                total_tasks=F("succeeded_tasks") + F("skipped_tasks"),
            ).exclude(state=JobState.FINISHED).update(state=JobState.FINISHED, stopped_at=now)

            finished_layers = Layer.objects.filter(
                id=instance.layer_id,
                total_tasks__gt=0,
                total_tasks=F("succeeded_tasks") + F("skipped_tasks"),
            ).exclude(state=JobState.FINISHED).update(state=JobState.FINISHED)

            # If the layer just finished, satisfy LAYER_ON_LAYER deps blocking on it
            if finished_layers:
                layer_blocking_deps = Dependency.objects.filter(
                    type=DependencyType.LAYER_ON_LAYER,
                    parent_layer_id=instance.layer_id,
                    is_satisfied=False,
                )
                _unblock_tasks_for_deps(layer_blocking_deps)

            # If the job just finished, satisfy JOB_ON_JOB deps blocking on it
            if finished_jobs:
                job_blocking_deps = Dependency.objects.filter(
                    type=DependencyType.JOB_ON_JOB,
                    parent_job_id=instance.job_id,
                    is_satisfied=False,
                )
                _unblock_tasks_for_deps(job_blocking_deps)

            # Check if failed (no tasks running/ready, and at least 1 failed task)
            Job.objects.filter(
                id=instance.job_id,
                running_tasks=0,
                ready_tasks=0,
                failed_tasks__gt=0,
            ).exclude(state__in=[JobState.FINISHED, JobState.FAILED]).update(state=JobState.FAILED, stopped_at=now)

            Layer.objects.filter(
                id=instance.layer_id,
                running_tasks=0,
                ready_tasks=0,
                failed_tasks__gt=0,
            ).exclude(state__in=[JobState.FINISHED, JobState.FAILED]).update(state=JobState.FAILED)


# ── Layer signals ──────────────────────────────────────────────────────────────


@receiver(pre_save, sender=Layer)
def layer_pre_save(sender, instance, update_fields=None, **kwargs):
    """Handle Layer state transitions for LAYER_ON_LAYER dependency satisfaction.

    When a Layer transitions to FINISHED, all LAYER_ON_LAYER dependencies
    blocking on it are satisfied, unblocking their dependent tasks directly.
    """
    if update_fields is not None and "state" not in update_fields:
        return

    # Only act on transitions — need to check old state
    if not instance.pk:
        return

    try:
        old_instance = Layer.objects.get(pk=instance.pk)
    except Layer.DoesNotExist:
        return

    if old_instance.state != instance.state and instance.state == JobState.FINISHED:
        deps = Dependency.objects.filter(
            type=DependencyType.LAYER_ON_LAYER,
            parent_layer_id=instance.pk,
            is_satisfied=False,
        )
        _unblock_tasks_for_deps(deps)


# ── Job signals ────────────────────────────────────────────────────────────────


@receiver(pre_save, sender=Job)
def job_pre_save(sender, instance, update_fields=None, **kwargs):
    """Handle Job state transitions for JOB_ON_JOB dependency satisfaction.

    When a Job transitions to FINISHED, all JOB_ON_JOB dependencies blocking
    on it are satisfied, unblocking their dependent tasks directly.
    """
    if update_fields is not None and "state" not in update_fields:
        return

    if not instance.pk:
        return

    try:
        old_instance = Job.objects.get(pk=instance.pk)
    except Job.DoesNotExist:
        return

    if old_instance.state != instance.state and instance.state == JobState.FINISHED:
        deps = Dependency.objects.filter(
            type=DependencyType.JOB_ON_JOB,
            parent_job_id=instance.pk,
            is_satisfied=False,
        )
        _unblock_tasks_for_deps(deps)
