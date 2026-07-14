from django.db import transaction
from django.db.models import F
from django.db.models.signals import post_save, pre_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Dependency, Frame, FrameState, Job, Layer


@receiver(post_save, sender=Dependency)
def dependency_post_save(sender, instance, created, **kwargs):
    """
    Handle dependency creation and satisfaction.
    """
    if created and not instance.is_satisfied:
        if instance.dep_frame_id:
            Frame.objects.filter(id=instance.dep_frame_id).update(depend_count=F("depend_count") + 1)


@receiver(pre_save, sender=Dependency)
def dependency_pre_save(sender, instance, **kwargs):
    """
    Handle dependency satisfaction updates.
    """
    if instance.id:
        try:
            old_instance = Dependency.objects.get(id=instance.id)
            if not old_instance.is_satisfied and instance.is_satisfied:
                if instance.dep_frame_id:
                    with transaction.atomic():
                        # Use select_for_update to lock the row while we evaluate it
                        frame = Frame.objects.select_for_update().get(id=instance.dep_frame_id)
                        frame.depend_count -= 1
                        if frame.depend_count == 0 and frame.state == FrameState.WAITING:
                            frame.state = FrameState.READY
                        frame.save(update_fields=["depend_count", "state", "updated_at"])
        except Dependency.DoesNotExist:
            pass


@receiver(pre_delete, sender=Dependency)
def dependency_pre_delete(sender, instance, **kwargs):
    """
    Repair depend_count before a dependency is destroyed.
    Must be pre_delete so the dep_frame_id is still available before CASCADE.
    """
    if not instance.is_satisfied and instance.dep_frame_id:
        with transaction.atomic():
            try:
                frame = Frame.objects.select_for_update().get(id=instance.dep_frame_id)
                frame.depend_count -= 1
                if frame.depend_count == 0 and frame.state == FrameState.WAITING:
                    frame.state = FrameState.READY
                frame.save(update_fields=["depend_count", "state", "updated_at"])
            except Frame.DoesNotExist:
                pass


@receiver(pre_save, sender=Frame)
def frame_pre_save(sender, instance, update_fields=None, **kwargs):
    """
    Handle Frame state transitions:
    1. Update parent Job and Layer counter caches.
    2. Resolve dependencies if frame SUCCEEDED or SKIPPED.
    """
    # Fast-exit: if update_fields is specified and "state" is not in it, there
    # is no state transition to process. Skips the DB round-trip for saves that
    # only touch depend_count, checkpoint_count, or other non-state fields.
    if update_fields is not None and "state" not in update_fields:
        return

    try:
        old_instance = Frame.objects.get(id=instance.id)
    except Frame.DoesNotExist:
        # NOTE: In the standard job submission flow, frames are created via
        # Frame.objects.bulk_create(), which bypasses signals entirely. The
        # counter updates for that path are handled manually in services.py.
        # This block only fires when a Frame is created via .create() or a
        # direct .save() call (e.g., from FrameFactory in tests or a management
        # command). Do NOT also update counters elsewhere for that code path.
        state_field = (
            "running_frames" if instance.state == FrameState.CHECKPOINT else f"{instance.state.lower()}_frames"
        )
        Layer.objects.filter(id=instance.layer_id).update(
            **{state_field: F(state_field) + 1},
            total_frames=F("total_frames") + 1,
        )
        Job.objects.filter(id=instance.job_id).update(
            **{state_field: F(state_field) + 1},
            total_frames=F("total_frames") + 1,
        )
        return

    if old_instance.state != instance.state:
        # State changed. Update parent counters atomically using F() expressions
        old_state_field = (
            "running_frames" if old_instance.state == FrameState.CHECKPOINT else f"{old_instance.state.lower()}_frames"
        )
        new_state_field = (
            "running_frames" if instance.state == FrameState.CHECKPOINT else f"{instance.state.lower()}_frames"
        )

        if old_state_field != new_state_field:
            Layer.objects.filter(id=instance.layer_id).update(
                **{old_state_field: F(old_state_field) - 1, new_state_field: F(new_state_field) + 1}
            )
            Job.objects.filter(id=instance.job_id).update(
                **{old_state_field: F(old_state_field) - 1, new_state_field: F(new_state_field) + 1}
            )

        # If transitioning to SUCCEEDED or SKIPPED, satisfy dependencies blocking other frames
        if instance.state in (FrameState.SUCCEEDED, FrameState.SKIPPED):
            # Record stop time
            instance.stopped_at = timezone.now()

            # Find and satisfy dependencies waiting on this frame
            deps = Dependency.objects.filter(parent_frame_id=instance.id, is_satisfied=False)
            for dep in deps:
                dep.is_satisfied = True
                dep.satisfied_at = timezone.now()
                dep.save()  # will trigger dependency_pre_save which handles depend_count
