from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView
from devlink_backend.auth_views import token_obtain_pair
from devlink_backend.dev_panel import dev_logs_json, dev_panel


def health(request):
    return JsonResponse({"status": "ok", "service": "devlink-backend"})


urlpatterns = [
    path("", health, name="root-health"),
    path("healthz/", health, name="healthz"),
    path("admin/", admin.site.urls),
    path("devlink-debug/", dev_panel, name="devlink-debug"),
    path("devlink-debug/logs.json", dev_logs_json, name="devlink-debug-logs"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/auth/login/", token_obtain_pair, name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/", include("accounts.urls")),
    path("api/", include("devices.urls")),
    path("api/", include("projects.urls")),
    path("api/", include("sessions.urls")),
    path("api/", include("tasks.urls")),
    path("api/", include("agents.urls")),
    path("api/", include("terminals.urls")),
]
