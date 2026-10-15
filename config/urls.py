from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from core.views import HealthView
from accounts.views import account_link
from dashboard import views as dashboard

urlpatterns = [
    path('', dashboard.home),
    path('dashboard/', include('dashboard.urls')),
    path('events/<int:item_id>/', dashboard.detail, {'kind': 'event'}),
    path('services/<int:item_id>/', dashboard.detail, {'kind': 'service'}),
    path("account-link/", account_link),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("catalog.urls")),
    path("api/v1/", include("notifications.urls")),
    path("api/v1/health/", HealthView.as_view(), name="health"),
    path("api/v1/schema/", SpectacularAPIView.as_view(permission_classes=[]), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[]), name="docs"),
]
