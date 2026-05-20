from django.urls import path

from .views import (
    AgentSessionCloseView,
    AgentSessionDetailView,
    AgentSessionEmergencyStopView,
    AgentSessionForkView,
    AgentSessionListCreateView,
    AgentSessionSettingsView,
    SessionAttachmentView,
    SessionMessageCreateView,
    SessionSearchView,
    SessionTimelineView,
    WorkspaceBootstrapView,
)

urlpatterns = [
    path("workspace/bootstrap/", WorkspaceBootstrapView.as_view(), name="workspace-bootstrap"),
    path("sessions/search/", SessionSearchView.as_view(), name="session-search"),
    path("sessions/", AgentSessionListCreateView.as_view(), name="session-list-create"),
    path("sessions/<uuid:pk>/", AgentSessionDetailView.as_view(), name="session-detail"),
    path("sessions/<uuid:pk>/close/", AgentSessionCloseView.as_view(), name="session-close"),
    path("sessions/<uuid:pk>/emergency-stop/", AgentSessionEmergencyStopView.as_view(), name="session-emergency-stop"),
    path("sessions/<uuid:pk>/fork/", AgentSessionForkView.as_view(), name="session-fork"),
    path("sessions/<uuid:pk>/settings/", AgentSessionSettingsView.as_view(), name="session-settings"),
    path("sessions/<uuid:pk>/attachments/", SessionAttachmentView.as_view(), name="session-attachments"),
    path("sessions/<uuid:pk>/timeline/", SessionTimelineView.as_view(), name="session-timeline"),
    path("sessions/<uuid:pk>/messages/", SessionMessageCreateView.as_view(), name="session-message-create"),
]
