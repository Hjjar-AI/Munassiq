from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from core.views import HealthView

urlpatterns = [
    path("api/v1/health/", HealthView.as_view(), name="health"),
    path("api/v1/schema/", SpectacularAPIView.as_view(permission_classes=[]), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[]), name="docs"),
]
