from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClusterTelemetryHistoryView,
    DispatchTraceViewSet,
    FarmEventViewSet,
    TaskLogViewSet,
)

router = DefaultRouter()
router.register(r"dispatches", DispatchTraceViewSet, basename="telemetry-dispatch")
router.register(r"events", FarmEventViewSet, basename="telemetry-event")
router.register(r"logs", TaskLogViewSet, basename="telemetry-log")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "tasks/<uuid:task_pk>/logs/",
        TaskLogViewSet.as_view({"get": "list", "post": "create"}),
        name="task-logs-list",
    ),
    path("tasks/<uuid:task_pk>/logs/latest/", TaskLogViewSet.as_view({"get": "latest"}), name="task-logs-latest"),
    path("jobs/<uuid:job_pk>/logs/", TaskLogViewSet.as_view({"get": "list"}), name="job-logs-list"),
    path("cluster/history/", ClusterTelemetryHistoryView.as_view(), name="cluster-telemetry-history"),
]
