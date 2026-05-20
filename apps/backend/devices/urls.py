from django.urls import path

from .views import (
    CliHeartbeatView,
    CliCapabilitiesView,
    DeviceCapabilitiesRefreshView,
    DeviceCapabilitiesView,
    DeviceDetailView,
    DeviceListView,
    PairDeviceView,
    PairingCodeCreateView,
)

urlpatterns = [
    path("pairing-codes/", PairingCodeCreateView.as_view(), name="pairing-code-create"),
    path("cli/pair/", PairDeviceView.as_view(), name="cli-pair"),
    path("cli/heartbeat/", CliHeartbeatView.as_view(), name="cli-heartbeat"),
    path("cli/capabilities/", CliCapabilitiesView.as_view(), name="cli-capabilities"),
    path("devices/", DeviceListView.as_view(), name="device-list"),
    path("devices/<uuid:pk>/capabilities/", DeviceCapabilitiesView.as_view(), name="device-capabilities"),
    path("devices/<uuid:pk>/capabilities/refresh/", DeviceCapabilitiesRefreshView.as_view(), name="device-capabilities-refresh"),
    path("devices/<uuid:pk>/", DeviceDetailView.as_view(), name="device-detail"),
]
