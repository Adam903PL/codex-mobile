from django.db import connection, transaction
from rest_framework import filters, generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.auth import DeviceTokenAuthentication

from .filters import TaskFilter
from .models import Task, TaskEvent
from .serializers import (
    ClaimedTaskSerializer,
    CliTaskStatusSerializer,
    FinishTaskSerializer,
    TaskCreateSerializer,
    TaskEventSerializer,
    TaskSerializer,
)
from .services import create_task_event, transition_task
from sessions.services import create_assistant_message_for_task


class TaskListCreateView(generics.ListCreateAPIView):
    filterset_class = TaskFilter
    ordering_fields = ["created_at", "updated_at", "status"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return TaskCreateSerializer
        return TaskSerializer

    def get_queryset(self):
        return Task.objects.select_related("device", "project", "session").filter(owner=self.request.user)


class TaskDetailView(generics.RetrieveAPIView):
    serializer_class = TaskSerializer

    def get_queryset(self):
        return Task.objects.select_related("device", "project", "session").filter(owner=self.request.user)


class TaskCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        task = generics.get_object_or_404(Task, pk=pk, owner=request.user)
        task = transition_task(task, Task.Status.CANCELED, message="Task canceled")
        return Response(TaskSerializer(task).data)


class TaskEventListView(generics.ListAPIView):
    serializer_class = TaskEventSerializer
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["sequence", "created_at"]
    ordering = ["sequence"]
    pagination_class = None

    def get_queryset(self):
        task = generics.get_object_or_404(Task, pk=self.kwargs["pk"], owner=self.request.user)
        queryset = task.events.all()
        after = self.request.query_params.get("after")
        if after and after.isdigit():
            queryset = queryset.filter(sequence__gt=int(after))
        return queryset


class CliNextTaskView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def get(self, request):
        device = request.auth
        queryset = (
            Task.objects.filter(device=device, status=Task.Status.QUEUED)
        )
        if connection.features.has_select_for_update:
            kwargs = {"skip_locked": connection.features.has_select_for_update_skip_locked}
            if connection.features.has_select_for_update_of:
                kwargs["of"] = ("self",)
            queryset = queryset.select_for_update(**kwargs)
        task = queryset.order_by("created_at").first()
        if not task:
            return Response(status=status.HTTP_204_NO_CONTENT)

        task = transition_task(task, Task.Status.CLAIMED, message="Task claimed")
        task = Task.objects.select_related("project", "session", "device").get(pk=task.pk)
        return Response(ClaimedTaskSerializer(task).data)


class CliStartTaskView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        task = generics.get_object_or_404(Task, pk=pk, device=request.auth)
        task = transition_task(task, Task.Status.RUNNING, message="Task started")
        return Response(TaskSerializer(task).data)


class CliTaskStatusView(generics.RetrieveAPIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = CliTaskStatusSerializer

    def get_queryset(self):
        return Task.objects.filter(device=self.request.auth)


class CliTaskEventCreateView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        task = generics.get_object_or_404(Task, pk=pk, device=request.auth)
        serializer = TaskEventSerializer(data=request.data, context={"task": task})
        serializer.is_valid(raise_exception=True)
        event = serializer.save()
        return Response(TaskEventSerializer(event).data, status=status.HTTP_201_CREATED)


class CliFinishTaskView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        task = generics.get_object_or_404(Task, pk=pk, device=request.auth)
        serializer = FinishTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        task = transition_task(
            task,
            data["status"],
            message=f"Task finished with status {data['status']}",
            final_output=data.get("final_output", ""),
            exit_code=data.get("exit_code"),
            error_code=data.get("error_code", ""),
            error_message=data.get("error_message", ""),
        )
        create_task_event(
            task=task,
            event_type=TaskEvent.EventType.FINAL,
            message=task.final_output,
            payload={"status": task.status, "exit_code": task.exit_code, "kind": "final", "source": "backend"},
        ) if not task.events.filter(event_type=TaskEvent.EventType.FINAL).exists() else None
        create_assistant_message_for_task(task)
        return Response(TaskSerializer(task).data)
