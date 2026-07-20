from rest_framework import routers

from .views import WorkerNodeViewSet, WorkerPoolViewSet

router = routers.DefaultRouter()
router.register(r"workers", WorkerNodeViewSet, basename="worker")
router.register(r"pools", WorkerPoolViewSet, basename="pool")

urlpatterns = router.urls
