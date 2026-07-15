from rest_framework import routers
from .views import WorkerNodeViewSet

router = routers.DefaultRouter()
router.register(r"workers", WorkerNodeViewSet, basename="worker")

urlpatterns = router.urls
