"""
URL routing for the jobs app.

Uses drf-nested-routers to build the URL hierarchy:
    /api/jobs/
    /api/jobs/{job_pk}/layers/
    /api/jobs/{job_pk}/layers/{layer_pk}/tasks/
    /api/jobs/{job_pk}/dependencies/      — scoped dep list for a job
    /api/tasks/{id}/                      — top-level task for Worker action endpoints
    /api/dependencies/{id}/               — top-level dependency CRUD

Task state transition actions (start, succeed, fail, skip, checkpoint) are
registered on the top-level ``tasks`` router so that Worker daemons can
reach them with a single UUID, without needing to know the layer/job hierarchy.
"""

from django.urls import path
from rest_framework_nested import routers

from .views import DependencyViewSet, RecentDispatchesView, TaskDispatchView, TaskViewSet, JobViewSet, LayerViewSet

# ── Top-level router ──────────────────────────────────────────────────────────
router = routers.DefaultRouter()
router.register(r"jobs", JobViewSet, basename="job")
router.register(r"tasks", TaskViewSet, basename="task")
router.register(r"dependencies", DependencyViewSet, basename="dependency")

# ── Nested: jobs → layers ─────────────────────────────────────────────────────
jobs_router = routers.NestedDefaultRouter(router, r"jobs", lookup="job")
jobs_router.register(r"layers", LayerViewSet, basename="job-layer")
jobs_router.register(r"dependencies", DependencyViewSet, basename="job-dependency")

# ── Nested: layers → tasks ───────────────────────────────────────────────────
layers_router = routers.NestedDefaultRouter(jobs_router, r"layers", lookup="layer")
layers_router.register(r"tasks", TaskViewSet, basename="layer-task")

urlpatterns = (
    [
        path("tasks/dispatch/", TaskDispatchView.as_view(), name="task-dispatch"),
        path("tasks/recent-dispatches/", RecentDispatchesView.as_view(), name="task-recent-dispatches"),
    ]
    + router.urls
    + jobs_router.urls
    + layers_router.urls
)
