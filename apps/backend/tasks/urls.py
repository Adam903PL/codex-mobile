from django.urls import path

from .views import (
    CliFinishTaskView,
    CliNextTaskView,
    CliStartTaskView,
    CliTaskEventCreateView,
    CliTaskStatusView,
    TaskCancelView,
    TaskDetailView,
    TaskEventListView,
    TaskListCreateView,
)

urlpatterns = [
    path("tasks/", TaskListCreateView.as_view(), name="task-list-create"),
    path("tasks/<uuid:pk>/", TaskDetailView.as_view(), name="task-detail"),
    path("tasks/<uuid:pk>/cancel/", TaskCancelView.as_view(), name="task-cancel"),
    path("tasks/<uuid:pk>/events/", TaskEventListView.as_view(), name="task-events"),
    path("cli/tasks/next/", CliNextTaskView.as_view(), name="cli-next-task"),
    path("cli/tasks/<uuid:pk>/", CliTaskStatusView.as_view(), name="cli-task-status"),
    path("cli/tasks/<uuid:pk>/start/", CliStartTaskView.as_view(), name="cli-start-task"),
    path("cli/tasks/<uuid:pk>/events/", CliTaskEventCreateView.as_view(), name="cli-task-event"),
    path("cli/tasks/<uuid:pk>/finish/", CliFinishTaskView.as_view(), name="cli-finish-task"),
]
