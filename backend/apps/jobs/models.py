import uuid

from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import (
    CASCADE, SET_NULL, BooleanField, CharField, DateTimeField, ForeignKey,
    Index, IntegerField, JSONField, PositiveIntegerField, TextChoices,
    TextField, UUIDField
)


class JobState(TextChoices):
    PENDING   = 'PENDING',  'Pending'   # Queued, not yet dispatching
    RUNNING   = 'RUNNING',  'Running'   # At least one frame is active
    FINISHED  = 'FINISHED', 'Finished'  # All frames succeeded
    FAILED    = 'FAILED',   'Failed'    # One or more frames failed beyond retries
    PAUSED    = 'PAUSED',   'Paused'    # Operator-suspended


class LayerType(TextChoices):
    RENDER    = 'RENDER', 'Render'      # Standard render pass (beauty, shadow, AO, etc.)
    UTIL      = 'UTIL',   'Utility'     # Pre/post processing script (file move, convert, etc.)
    POST      = 'POST',   'Post'        # Composite or delivery step (Nuke, FFmpeg, etc.)


class FrameState(TextChoices):
    WAITING     = 'WAITING',     'Waiting'       # Blocked by unresolved dependencies
    READY       = 'READY',       'Ready'         # Unblocked, awaiting a free Worker
    RUNNING     = 'RUNNING',     'Running'       # Actively executing on a Worker
    CHECKPOINT  = 'CHECKPOINT',  'Checkpointing' # Saving intermediate progress (e.g. V-Ray resume)
    SUCCEEDED   = 'SUCCEEDED',   'Succeeded'     # Completed with exit code 0
    FAILED      = 'FAILED',      'Failed'        # Terminated with non-zero exit status
    SKIPPED     = 'SKIPPED',     'Skipped'       # Failed but dismissed by a supervisor; unblocks dependents
    # SKIPPED: supervisor acknowledges the failure and removes the frame from retry.
    # The job can reach FINISHED even with skipped frames.


class DependencyType(TextChoices):
    JOB_ON_JOB       = 'JOB_ON_JOB',       'Job on Job'       
    LAYER_ON_LAYER   = 'LAYER_ON_LAYER',   'Layer on Layer'   
    FRAME_ON_FRAME   = 'FRAME_ON_FRAME',   'Frame on Frame'   


class Job(models.Model):
    """The top-level submission entity for a render.

    Attributes:
        id: UUID primary key.
        name: System-generated stable identifier.
        visible_name: Human-readable label shown in the UI.
        project: Active show or production segment.
        department: Department name (e.g. Lighting, FX).
        user: The submitter's display name.
        submitted_by: FK to User if submitted via the web.
        state: Current execution state.
        is_paused: Standalone pause flag.
        priority: Dispatch priority (1-100).
        max_frames_per_worker: Concurrent frames per worker limit.
        log_directory: Absolute path for frame logs.
        total_frames: Counter cache.
        waiting_frames: Counter cache.
        ready_frames: Counter cache.
        running_frames: Counter cache.
        succeeded_frames: Counter cache.
        failed_frames: Counter cache.
        skipped_frames: Counter cache.
        depend_frames: Counter cache.
        created_at: Timestamp.
        updated_at: Timestamp.
        stopped_at: Timestamp when state became FINISHED or FAILED.
    """
    id           = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = CharField(max_length=255, unique=True, db_index=True)
    visible_name = CharField(max_length=255, blank=True)
    
    project      = CharField(max_length=64, db_index=True)
    department   = CharField(max_length=64, blank=True, db_index=True)
    
    user         = CharField(
        max_length=64, 
        db_index=True,
        help_text="The submitter's display name. Defaults to the OS username in the DCC plugin but is manually editable. Matches Deadline's UserName field."
    )
    
    submitted_by = ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=SET_NULL, null=True, blank=True,
        related_name='submitted_jobs',
        help_text="Populated ONLY when submitted via the web frontend. NULL for DCC plugin submissions."
    )
    
    state        = CharField(max_length=16, choices=JobState.choices,
                             default=JobState.PENDING, db_index=True)
    is_paused    = BooleanField(default=False)
    
    priority     = IntegerField(
                       default=50, db_index=True,
                       validators=[MinValueValidator(1), MaxValueValidator(100)]
                   )
    
    max_frames_per_worker = PositiveIntegerField(
        default=1,
        verbose_name='max concurrent frames per worker'
    )
    
    log_directory = CharField(max_length=2048)
    
    total_frames     = IntegerField(default=0)
    waiting_frames   = IntegerField(default=0)
    ready_frames     = IntegerField(default=0)
    running_frames   = IntegerField(default=0)
    succeeded_frames = IntegerField(default=0)
    failed_frames    = IntegerField(default=0)
    skipped_frames   = IntegerField(default=0)
    depend_frames    = IntegerField(default=0)
    
    created_at   = DateTimeField(auto_now_add=True)
    updated_at   = DateTimeField(auto_now=True)
    stopped_at   = DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name        = 'job'
        verbose_name_plural = 'jobs'
        ordering = ['-priority', 'created_at']
        indexes = [
            Index(fields=['state', 'priority']),
            Index(fields=['project', 'state']), 
            Index(fields=['user', 'state']),    
        ]

    def __str__(self):
        return self.name


class Layer(models.Model):
    """A collection of frames that share the same command, requirements, and state.

    Attributes:
        id: UUID primary key.
        job: FK to parent Job.
        name: Name of the layer (e.g. 'beauty').
        layer_type: Dispatch and execution type.
        command: Base command template.
        frame_range: VFX frame range descriptor.
        chunk_size: Consecutive frames batched into one Frame.
        min_cores: Minimum CPU cores.
        min_memory_mb: Minimum RAM in MB.
        min_gpus: Minimum GPU count.
        tags: Worker compatibility tags array.
        scene_path: DCC scene file path.
        scene_info: DCC scene metadata JSON.
        env: Environment variable overrides JSON.
        max_retries: Per-frame retry ceiling.
        timeout_seconds: Frame execution timeout.
        state: Layer-level state.
        total_frames: Counter cache.
        waiting_frames: Counter cache.
        ready_frames: Counter cache.
        running_frames: Counter cache.
        succeeded_frames: Counter cache.
        failed_frames: Counter cache.
        skipped_frames: Counter cache.
        depend_frames: Counter cache.
    """
    id          = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job         = ForeignKey(Job, on_delete=CASCADE, related_name='layers')
    name        = CharField(max_length=256)
    
    layer_type  = CharField(
        max_length=8,
        choices=LayerType.choices,
        default=LayerType.RENDER,
        verbose_name='render pass type'
    )
    
    command     = TextField()
    frame_range = CharField(max_length=1024)
    chunk_size  = PositiveIntegerField(
        default=1,
        verbose_name='frames per chunk'
    )
    
    min_cores   = PositiveIntegerField(
        default=1,
        verbose_name='minimum CPU cores'
    )
    min_memory_mb = PositiveIntegerField(
        default=4096,
        verbose_name='minimum memory (MB)'
    )
    min_gpus    = PositiveIntegerField(
        default=0,
        verbose_name='minimum GPUs'
    )
    tags        = ArrayField(models.CharField(max_length=64), default=list, blank=True)
    
    scene_path  = CharField(max_length=2048, blank=True)
    scene_info  = JSONField(
        default=dict,
        blank=True,
        verbose_name='scene metadata'
    )
    env         = JSONField(default=dict, blank=True)
    
    max_retries = PositiveIntegerField(default=3)
    timeout_seconds = PositiveIntegerField(null=True, blank=True)
    
    state            = CharField(max_length=16, choices=JobState.choices,
                                 default=JobState.PENDING, db_index=True)
    
    total_frames     = IntegerField(default=0)
    waiting_frames   = IntegerField(default=0)
    ready_frames     = IntegerField(default=0)
    running_frames   = IntegerField(default=0)
    succeeded_frames = IntegerField(default=0)
    failed_frames    = IntegerField(default=0)
    skipped_frames   = IntegerField(default=0)
    depend_frames    = IntegerField(default=0)

    class Meta:
        verbose_name        = 'layer'
        verbose_name_plural = 'layers'
        unique_together = ('job', 'name')
        indexes = [
            Index(fields=['job', 'state']),
        ]

    def __str__(self):
        return f"{self.job.name} / {self.name}"


class Frame(models.Model):
    """The smallest schedulable unit of work within a Layer.

    Attributes:
        id: UUID primary key.
        layer: The parent Layer this frame belongs to.
        job: Denormalized FK to the parent Job for bulk operations.
        name: Derived display name, e.g. 'beauty_0042'.
        number: The render frame index (first frame of chunk for chunked layers).
        dispatch_order: Scheduler dispatch priority within the layer.
        state: Current execution state.
        depend_count: Counter of unresolved blocking dependencies.
        retries: Number of execution attempts so far.
        max_retries: Maximum allowed attempts before transitioning to FAILED.
        checkpoint_count: Number of resume checkpoints saved (e.g. V-Ray .vrimg).
        exit_status: Process exit code. -1 = not yet run.
        max_memory_used_mb: Peak RSS memory in MB reported by the Worker.
        cores_used: Actual CPU cores reserved at dispatch time.
        worker_name: Hostname of the executing Worker.
        started_at: Timestamp when execution began.
        stopped_at: Timestamp when execution ended.
        updated_at: Last modification timestamp.
    """
    id      = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    layer   = ForeignKey(Layer, on_delete=CASCADE, related_name='frames')
    job     = ForeignKey(Job, on_delete=CASCADE, related_name='frames')
    
    name    = CharField(max_length=256)
    number  = IntegerField(db_index=True)
    dispatch_order = IntegerField(default=0, db_index=True)
    
    state       = CharField(max_length=16, choices=FrameState.choices,
                            default=FrameState.WAITING, db_index=True)
    
    depend_count = IntegerField(
        default=0,
        db_index=True,
        verbose_name='dependency count'
    )
    
    retries     = PositiveIntegerField(default=0)
    max_retries = PositiveIntegerField(default=3)
    checkpoint_count = PositiveIntegerField(default=0)
    
    exit_status = IntegerField(default=-1)
    
    max_memory_used_mb = PositiveIntegerField(
        default=0,
        verbose_name='peak memory used (MB)'
    )
    cores_used  = PositiveIntegerField(null=True, blank=True)
    worker_name = CharField(
        max_length=256,
        null=True,
        blank=True,
        verbose_name='worker hostname'
    )
    
    started_at  = DateTimeField(null=True, blank=True)
    stopped_at  = DateTimeField(null=True, blank=True)
    updated_at  = DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'frame'
        verbose_name_plural = 'frames'
        unique_together = ('layer', 'number')
        indexes = [
            Index(fields=['job', 'state']),             
            Index(fields=['layer', 'state']),           
            Index(fields=['state', 'depend_count']),    
        ]

    def __str__(self):
        return self.name


class Dependency(models.Model):
    """Represents a blocking requirement between entities.

    Attributes:
        id: UUID primary key.
        type: Dependency kind (FRAME_ON_FRAME, LAYER_ON_LAYER, JOB_ON_JOB).
        dep_job: The blocked Job.
        dep_layer: The blocked Layer (optional).
        dep_frame: The blocked Frame (optional).
        parent_job: The blocking Job.
        parent_layer: The blocking Layer (optional).
        parent_frame: The blocking Frame (optional).
        is_satisfied: Status flag.
        created_at: Creation timestamp.
        satisfied_at: Satisfaction timestamp.
    """
    id   = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = CharField(max_length=24, choices=DependencyType.choices, db_index=True)
    
    dep_job   = ForeignKey(Job,   on_delete=CASCADE, related_name='blocked_dependencies')
    dep_layer = ForeignKey(Layer, on_delete=CASCADE, null=True, blank=True,
                           related_name='blocked_dependencies')
    dep_frame = ForeignKey(Frame, on_delete=CASCADE, null=True, blank=True,
                           related_name='blocked_dependencies')
                           
    parent_job   = ForeignKey(Job,   on_delete=CASCADE, related_name='blocking_dependencies')
    parent_layer = ForeignKey(Layer, on_delete=CASCADE, null=True, blank=True,
                              related_name='blocking_dependencies')
    parent_frame = ForeignKey(Frame, on_delete=CASCADE, null=True, blank=True,
                              related_name='blocking_dependencies')
                              
    is_satisfied = BooleanField(default=False, db_index=True)
    created_at   = DateTimeField(auto_now_add=True)
    satisfied_at = DateTimeField(null=True, blank=True)

    def clean(self):
        if self.type == DependencyType.FRAME_ON_FRAME:
            if not self.dep_frame_id or not self.parent_frame_id:
                raise ValidationError(
                    "FRAME_ON_FRAME dependency requires both dep_frame and parent_frame."
                )
            if self.dep_frame_id == self.parent_frame_id:
                raise ValidationError("A frame cannot depend on itself.")
        elif self.type == DependencyType.LAYER_ON_LAYER:
            if not self.dep_layer_id or not self.parent_layer_id:
                raise ValidationError(
                    "LAYER_ON_LAYER dependency requires both dep_layer and parent_layer."
                )
        elif self.type == DependencyType.JOB_ON_JOB:
            if not self.dep_job_id or not self.parent_job_id:
                raise ValidationError(
                    "JOB_ON_JOB dependency requires both dep_job and parent_job."
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name        = 'dependency'
        verbose_name_plural = 'dependencies'  
        indexes = [
            Index(fields=['parent_frame', 'is_satisfied']),  
            Index(fields=['parent_layer', 'is_satisfied']),  
            Index(fields=['parent_job',   'is_satisfied']),  
            Index(fields=['dep_frame',    'is_satisfied']),  
            Index(fields=['dep_layer',    'is_satisfied']),  
        ]
