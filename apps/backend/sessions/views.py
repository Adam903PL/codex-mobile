from __future__ import annotations

from itertools import chain

from django.db.models import Count, Prefetch, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.models import Device
from devices.serializers import DeviceSerializer
from agents.models import ApprovalRequest
from agents.serializers import ApprovalRequestSerializer
from projects.models import Project
from projects.serializers import ProjectSerializer
from tasks.models import Task, TaskEvent
from tasks.serializers import TaskSerializer
from tasks.services import create_task_event, transition_task
from terminals.models import TerminalEvent, TerminalInput, TerminalSession
from terminals.services import ACTIVE_STATUSES, create_terminal_event, create_terminal_input

from .models import AgentSession, SessionMessage
from .serializers import (
    AgentSessionCreateSerializer,
    AgentSessionSerializer,
    AgentSessionUpdateSerializer,
    SessionMessageCreateSerializer,
    SessionMessageSerializer,
    SessionSettingsSerializer,
)
from .services import (
    broadcast_session_timeline,
    timeline_item_for_event,
    timeline_item_for_message,
    touch_session,
)


class WorkspaceBootstrapView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        devices = Device.objects.filter(owner=request.user).annotate(project_count=Count("projects"))
        projects = Project.objects.select_related("device").filter(owner=request.user, is_active=True)
        latest_session = (
            AgentSession.objects.select_related("device", "project", "parent_session")
            .annotate(task_count=Count("tasks"))
            .filter(owner=request.user, status=AgentSession.Status.OPEN)
            .order_by("-last_activity_at", "-created_at")
            .first()
        )
        return Response(
            {
                "account": {
                    "id": request.user.id,
                    "username": request.user.get_username(),
                },
                "devices": DeviceSerializer(devices, many=True).data,
                "projects": ProjectSerializer(projects, many=True).data,
                "pending_approvals": ApprovalRequestSerializer(
                    ApprovalRequest.objects.select_related("device", "project", "session", "task").filter(
                        owner=request.user,
                        status__in=[
                            ApprovalRequest.Status.PENDING,
                            ApprovalRequest.Status.APPROVED,
                            ApprovalRequest.Status.RUNNING,
                        ],
                    )[:20],
                    many=True,
                ).data,
                "latest_session": (
                    AgentSessionSerializer(latest_session, context={"request": request}).data
                    if latest_session
                    else None
                ),
            }
        )


class AgentSessionListCreateView(generics.ListCreateAPIView):
    ordering_fields = ["created_at", "updated_at", "last_activity_at", "status"]
    ordering = ["-last_activity_at", "-created_at"]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AgentSessionCreateSerializer
        return AgentSessionSerializer

    def get_queryset(self):
        queryset = (
            AgentSession.objects.select_related("device", "project", "parent_session")
            .annotate(task_count=Count("tasks"))
            .filter(owner=self.request.user)
        )
        for field in ("project", "device", "status", "agent_type"):
            value = self.request.query_params.get(field)
            if value:
                queryset = queryset.filter(**{field: value})
        ordering = self.request.query_params.get("ordering")
        allowed = {
            "created_at",
            "-created_at",
            "updated_at",
            "-updated_at",
            "last_activity_at",
            "-last_activity_at",
            "status",
            "-status",
        }
        if ordering in allowed:
            queryset = queryset.order_by(ordering)
        else:
            queryset = queryset.order_by("-last_activity_at", "-created_at")
        return queryset

    def perform_create(self, serializer):
        project = serializer.validated_data["project"]
        title = serializer.validated_data.get("title") or project.name
        serializer.save(
            owner=self.request.user,
            device=project.device,
            title=title,
            model=serializer.validated_data.get("model", project.default_model),
            profile=serializer.validated_data.get("profile", project.default_profile),
            sandbox=serializer.validated_data.get("sandbox", project.default_sandbox),
            approval_policy=serializer.validated_data.get("approval_policy", project.default_approval_policy),
            last_activity_at=timezone.now(),
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        read_serializer = AgentSessionSerializer(
            self.get_queryset().get(pk=serializer.instance.pk),
            context=self.get_serializer_context(),
        )
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


class AgentSessionDetailView(generics.RetrieveUpdateAPIView):
    def get_serializer_class(self):
        if self.request.method in {"PATCH", "PUT"}:
            return AgentSessionUpdateSerializer
        return AgentSessionSerializer

    def get_queryset(self):
        return (
            AgentSession.objects.select_related("device", "project", "parent_session")
            .annotate(task_count=Count("tasks"))
            .filter(owner=self.request.user)
        )

    def partial_update(self, request, *args, **kwargs):
        response = super().partial_update(request, *args, **kwargs)
        session = self.get_queryset().get(pk=self.kwargs["pk"])
        response.data = AgentSessionSerializer(session, context=self.get_serializer_context()).data
        return response


class AgentSessionSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        session = generics.get_object_or_404(AgentSession, pk=pk, owner=request.user)
        serializer = SessionSettingsSerializer(session, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        touch_session(session)
        session.refresh_from_db()
        payload = AgentSessionSerializer(session, context={"request": request}).data
        broadcast_session_timeline(
            session,
            {
                "kind": "status",
                "id": f"settings-{session.updated_at.timestamp()}",
                "task_id": None,
                "sequence": 0,
                "content": "Session settings updated",
                "payload": {"settings": serializer.validated_data},
                "created_at": session.updated_at.isoformat(),
            },
        )
        return Response(payload)


class SessionAttachmentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        session = generics.get_object_or_404(AgentSession, pk=pk, owner=request.user)
        tool_settings = session.tool_settings if isinstance(session.tool_settings, dict) else {}
        return Response(
            {
                "images": tool_settings.get("images") or [],
                "attachments": tool_settings.get("attachments") or [],
            }
        )

    def post(self, request, pk):
        session = generics.get_object_or_404(AgentSession, pk=pk, owner=request.user)
        path = str(request.data.get("path") or "").strip()
        attachment_type = str(request.data.get("type") or "image").strip() or "image"
        if not path:
            raise ValidationError({"path": ["Path is required."]})
        tool_settings = session.tool_settings if isinstance(session.tool_settings, dict) else {}
        attachments = list(tool_settings.get("attachments") or [])
        record = {"path": path, "type": attachment_type}
        if record not in attachments:
            attachments.append(record)
        tool_settings["attachments"] = attachments
        if attachment_type == "image":
            images = [str(item) for item in tool_settings.get("images") or [] if str(item).strip()]
            if path not in images:
                images.append(path)
            tool_settings["images"] = images
        session.tool_settings = tool_settings
        session.save(update_fields=["tool_settings", "updated_at"])
        touch_session(session)
        return Response({"images": tool_settings.get("images") or [], "attachments": attachments}, status=status.HTTP_201_CREATED)


class AgentSessionCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = generics.get_object_or_404(AgentSession, pk=pk, owner=request.user)
        session.status = AgentSession.Status.CLOSED
        session.save(update_fields=["status", "updated_at"])
        return Response(AgentSessionSerializer(_session_queryset(request.user).get(pk=session.pk), context={"request": request}).data)


class AgentSessionForkView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        parent = generics.get_object_or_404(
            AgentSession.objects.select_related("device", "project"),
            pk=pk,
            owner=request.user,
        )
        if not parent.project.is_active:
            raise ValidationError({"project": ["Projekt jest nieaktywny."]})
        if parent.device.status == "revoked":
            raise ValidationError({"device": ["Urzadzenie projektu zostalo odlaczone."]})
        title = request.data.get("title") or f"Fork: {parent.title or parent.project.name}"
        child = AgentSession.objects.create(
            owner=request.user,
            device=parent.device,
            project=parent.project,
            parent_session=parent,
            agent_type=parent.agent_type,
            title=title,
            summary=parent.summary,
            model=parent.model,
            profile=parent.profile,
            sandbox=parent.sandbox,
            approval_policy=parent.approval_policy,
            git_branch=parent.git_branch,
            add_dirs=parent.add_dirs,
            model_settings=parent.model_settings,
            selected_skills=parent.selected_skills,
            web_search_enabled=parent.web_search_enabled,
            tool_settings=parent.tool_settings,
            last_activity_at=timezone.now(),
        )
        return Response(
            AgentSessionSerializer(_session_queryset(request.user).get(pk=child.pk), context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class AgentSessionEmergencyStopView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = generics.get_object_or_404(
            AgentSession.objects.select_related("device", "project"),
            pk=pk,
            owner=request.user,
        )
        canceled_tasks = []
        active_statuses = [Task.Status.QUEUED, Task.Status.CLAIMED, Task.Status.RUNNING]
        for task in Task.objects.filter(session=session, owner=request.user, status__in=active_statuses).order_by("created_at"):
            try:
                task = transition_task(
                    task,
                    Task.Status.CANCELED,
                    message="Task canceled by emergency stop",
                    event_payload={
                        "status": Task.Status.CANCELED,
                        "kind": "status",
                        "source": "emergency_stop",
                        "reason": "emergency_stop",
                    },
                )
            except ValidationError:
                continue
            canceled_tasks.append(str(task.id))

        killed_terminals = []
        terminals = TerminalSession.objects.filter(
            owner=request.user,
            device=session.device,
            project=session.project,
            status__in=ACTIVE_STATUSES,
        ).order_by("created_at")
        for terminal in terminals:
            if terminal.is_terminal:
                continue
            killed_terminals.append(str(terminal.id))
            if terminal.status == TerminalSession.Status.QUEUED:
                terminal.kill_requested = True
                terminal.status = TerminalSession.Status.KILLED
                terminal.finished_at = timezone.now()
                terminal.last_activity_at = terminal.finished_at
                terminal.save(update_fields=["kill_requested", "status", "finished_at", "last_activity_at", "updated_at"])
                create_terminal_event(
                    terminal,
                    kind=TerminalEvent.Kind.STATUS,
                    data="Terminal killed by emergency stop before local CLI claimed it",
                    payload={"status": terminal.status, "kill_requested": True, "reason": "emergency_stop"},
                )
                continue
            if not terminal.kill_requested:
                create_terminal_input(terminal, kind=TerminalInput.Kind.KILL)
                create_terminal_event(
                    terminal,
                    kind=TerminalEvent.Kind.STATUS,
                    data="Terminal kill requested by emergency stop",
                    payload={"status": terminal.status, "kill_requested": True, "reason": "emergency_stop"},
                )

        return Response(
            {
                "status": "stopped",
                "canceled_tasks": canceled_tasks,
                "killed_terminals": killed_terminals,
            }
        )


class SessionTimelineView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        session = generics.get_object_or_404(AgentSession, pk=pk, owner=request.user)
        messages = session.messages.select_related("task").all()
        tasks = Task.objects.filter(session=session).prefetch_related(
            Prefetch("events", queryset=TaskEvent.objects.order_by("sequence"))
        )
        event_items = [
            timeline_item_for_event(event)
            for task in tasks
            for event in task.events.all()
        ]
        message_items = [timeline_item_for_message(message) for message in messages]
        items = sorted(
            chain(message_items, event_items),
            key=lambda item: (item["created_at"], item.get("event_id") or item.get("message_id") or ""),
        )
        for index, item in enumerate(items, start=1):
            item["sequence"] = index
        after = request.query_params.get("after")
        if after and after.isdigit():
            items = [item for item in items if item["sequence"] > int(after)]
        return Response(items)


class SessionMessageCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        session = generics.get_object_or_404(
            AgentSession.objects.select_related("device", "project"),
            pk=pk,
            owner=request.user,
        )
        if session.status == AgentSession.Status.CLOSED:
            raise ValidationError({"session": ["Sesja jest zamknieta."]})
        if not session.project.is_active:
            raise ValidationError({"project": ["Projekt jest nieaktywny."]})
        if session.device.status == "revoked":
            raise ValidationError({"device": ["Urzadzenie projektu zostalo odlaczone."]})

        serializer = SessionMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        settings_overrides = data.get("settings_overrides")
        selected_skill_ids = data.get("selected_skill_ids")
        if settings_overrides:
            settings_serializer = SessionSettingsSerializer(session, data=settings_overrides, partial=True)
            settings_serializer.is_valid(raise_exception=True)
            settings_serializer.save()
        if selected_skill_ids is not None:
            session.selected_skills = [str(skill_id) for skill_id in selected_skill_ids]
            session.save(update_fields=["selected_skills", "updated_at"])

        task = Task.objects.create(
            owner=request.user,
            device=session.device,
            project=session.project,
            session=session,
            prompt=data["content"],
            agent_type=session.agent_type,
        )
        message = SessionMessage.objects.create(
            session=session,
            task=task,
            role=SessionMessage.Role.USER,
            content=data["content"],
            status=SessionMessage.Status.SENT,
            metadata={"settings_overrides": settings_overrides or {}, "selected_skill_ids": selected_skill_ids or session.selected_skills},
        )
        if not session.title or session.title == session.project.name:
            session.title = data["content"][:80]
        session.last_activity_at = timezone.now()
        session.save(update_fields=["title", "last_activity_at", "updated_at"])
        broadcast_session_timeline(session, timeline_item_for_message(message))
        create_task_event(
            task=task,
            event_type=TaskEvent.EventType.STATUS,
            message="Task queued",
            payload={"status": Task.Status.QUEUED, "to": Task.Status.QUEUED, "kind": "queued", "source": "backend"},
        )
        return Response(
            {
                "message": SessionMessageSerializer(message).data,
                "task": TaskSerializer(task).data,
                "session": AgentSessionSerializer(_session_queryset(request.user).get(pk=session.pk), context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class SessionSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if not q or len(q) < 2:
            return Response([])
        queryset = (
            AgentSession.objects.select_related("device", "project", "parent_session")
            .annotate(task_count=Count("tasks", distinct=True))
            .filter(owner=request.user)
            .filter(
                Q(title__icontains=q)
                | Q(summary__icontains=q)
                | Q(messages__content__icontains=q)
            )
            .distinct()
            .order_by("-last_activity_at", "-created_at")
        )
        return Response(AgentSessionSerializer(queryset[:30], many=True, context={"request": request}).data)


def _session_queryset(user):
    return (
        AgentSession.objects.select_related("device", "project", "parent_session")
        .annotate(task_count=Count("tasks"))
        .filter(owner=user)
    )
