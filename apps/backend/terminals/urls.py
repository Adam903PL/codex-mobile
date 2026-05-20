from django.urls import path

from .views import (
    CliNextTerminalSessionView,
    CliTerminalEventCreateView,
    CliTerminalInputListView,
    TerminalEventListView,
    TerminalInputView,
    TerminalKillView,
    TerminalResizeView,
    TerminalSessionCreateView,
    TerminalSessionDetailView,
)

urlpatterns = [
    path("terminal/sessions/", TerminalSessionCreateView.as_view(), name="terminal-session-create"),
    path("terminal/sessions/<uuid:pk>/", TerminalSessionDetailView.as_view(), name="terminal-session-detail"),
    path("terminal/sessions/<uuid:pk>/events/", TerminalEventListView.as_view(), name="terminal-event-list"),
    path("terminal/sessions/<uuid:pk>/input/", TerminalInputView.as_view(), name="terminal-input"),
    path("terminal/sessions/<uuid:pk>/resize/", TerminalResizeView.as_view(), name="terminal-resize"),
    path("terminal/sessions/<uuid:pk>/kill/", TerminalKillView.as_view(), name="terminal-kill"),
    path("cli/terminal/sessions/next/", CliNextTerminalSessionView.as_view(), name="cli-terminal-next"),
    path("cli/terminal/sessions/<uuid:pk>/input/", CliTerminalInputListView.as_view(), name="cli-terminal-input"),
    path("cli/terminal/sessions/<uuid:pk>/events/", CliTerminalEventCreateView.as_view(), name="cli-terminal-event"),
]
