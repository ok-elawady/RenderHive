import datetime

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.telemetry.models import DispatchTrace, FarmEvent, TaskExecutionLog, WorkerMetricSnapshot


class Command(BaseCommand):
    help = "Prune old telemetry logs, dispatch traces, farm events, and metric samples."

    def add_arguments(self, parser):
        default_days = getattr(settings, "TELEMETRY_RETENTION_DAYS", 30)
        parser.add_argument(
            "--days",
            type=int,
            default=default_days,
            help=f"Delete records older than this many days (default: {default_days}).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many records would be deleted without actually removing them.",
        )
        parser.add_argument(
            "--logs-only",
            action="store_true",
            help="Only prune task execution logs.",
        )
        parser.add_argument(
            "--metrics-only",
            action="store_true",
            help="Only prune worker metric snapshots.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        logs_only = options["logs_only"]
        metrics_only = options["metrics_only"]

        cutoff_date = timezone.now() - datetime.timedelta(days=days)
        self.stdout.write(f"Pruning records older than {days} days (cutoff: {cutoff_date.isoformat()})...")

        targets = []
        if not metrics_only:
            targets.append(("Task Logs", TaskExecutionLog.objects.filter(created_at__lt=cutoff_date)))
        if not logs_only and not metrics_only:
            targets.append(("Dispatch Traces", DispatchTrace.objects.filter(dispatched_at__lt=cutoff_date)))
            targets.append(("Farm Events", FarmEvent.objects.filter(created_at__lt=cutoff_date)))
        if not logs_only:
            targets.append(("Metric Snapshots", WorkerMetricSnapshot.objects.filter(recorded_at__lt=cutoff_date)))

        for label, qs in targets:
            count = qs.count()
            if dry_run:
                self.stdout.write(self.style.WARNING(f"[DRY-RUN] {label}: {count} records would be deleted."))
            else:
                deleted, _ = qs.delete()
                self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} {label}."))

        self.stdout.write(self.style.SUCCESS("Telemetry pruning complete."))
