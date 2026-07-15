"""
URL routing for the jobs app.

Uses drf-nested-routers to build the URL hierarchy:
    /api/jobs/
    /api/jobs/{job_pk}/layers/
    /api/jobs/{job_pk}/layers/{layer_pk}/frames/
    /api/frames/{id}/         — top-level frame for Worker action endpoints

Frame state transition actions (start, succeed, fail, skip, checkpoint) are
registered on the top-level ``frames`` router so that Worker daemons can
reach them with a single UUID, without needing to know the layer/job hierarchy.
"""

from django.urls import path
from rest_framework_nested import routers

from .views import FrameViewSet, JobViewSet, LayerViewSet, FrameDispatchView

# ── Top-level router ──────────────────────────────────────────────────────────
router = routers.DefaultRouter()
router.register(r"jobs", JobViewSet, basename="job")
router.register(r"frames", FrameViewSet, basename="frame")

# ── Nested: jobs → layers ─────────────────────────────────────────────────────
jobs_router = routers.NestedDefaultRouter(router, r"jobs", lookup="job")
jobs_router.register(r"layers", LayerViewSet, basename="job-layer")

# ── Nested: layers → frames ───────────────────────────────────────────────────
layers_router = routers.NestedDefaultRouter(jobs_router, r"layers", lookup="layer")
layers_router.register(r"frames", FrameViewSet, basename="layer-frame")

urlpatterns = [
    path("frames/dispatch/", FrameDispatchView.as_view(), name="frame-dispatch"),
] + router.urls + jobs_router.urls + layers_router.urls
