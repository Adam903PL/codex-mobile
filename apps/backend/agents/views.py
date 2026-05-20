from __future__ import annotations

from django.db import connection, transaction
from django.db.models import Q
from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.auth import DeviceTokenAuthentication
from devices.models import Device
from projects.models import Project
from sessions.serializers import SessionSettingsSerializer

from .command_catalog import command_catalog, get_command, slash_commands
from .models import ApprovalRequest
from .serializers import (
    ApprovalFinishSerializer,
    ApprovalRequestCreateSerializer,
    ApprovalRequestSerializer,
    CliApprovalRequestSerializer,
    mark_decided,
)


class ApprovalRequestListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ApprovalRequestCreateSerializer
        return ApprovalRequestSerializer

    def get_queryset(self):
        queryset = (
            ApprovalRequest.objects.select_related("device", "project", "session", "task")
            .filter(owner=self.request.user)
            .order_by("-requested_at")
        )
        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approval = serializer.save()
        return Response(ApprovalRequestSerializer(approval).data, status=status.HTTP_201_CREATED)


class CodexCommandCatalogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"commands": command_catalog(), "slash_commands": slash_commands()})


class CodexActionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        command_id = str(request.data.get("command_id") or "").strip()
        command = get_command(command_id)
        if not command:
            return Response({"message": "Nieznana komenda Codexa."}, status=status.HTTP_400_BAD_REQUEST)

        arguments = request.data.get("arguments") if isinstance(request.data.get("arguments"), dict) else {}
        project = None
        device = None
        project_id = request.data.get("project")
        device_id = request.data.get("device")
        if project_id:
            project = generics.get_object_or_404(Project.objects.select_related("device"), pk=project_id, owner=request.user, is_active=True)
            device = project.device
        elif device_id:
            device = generics.get_object_or_404(Device, pk=device_id, owner=request.user)
        else:
            device = Device.objects.filter(owner=request.user).order_by("-last_seen_at", "-updated_at").first()

        if command["requires_project"] and not project:
            return Response({"message": "Ta komenda wymaga wybranego projektu."}, status=status.HTTP_400_BAD_REQUEST)
        if not device:
            return Response({"message": "Najpierw sparuj i uruchom lokalne CLI."}, status=status.HTTP_400_BAD_REQUEST)

        status_value = ApprovalRequest.Status.PENDING if command["requires_approval"] else ApprovalRequest.Status.APPROVED
        approval = ApprovalRequest.objects.create(
            owner=request.user,
            device=device,
            project=project,
            session_id=request.data.get("session") or None,
            command_id=command_id,
            action_type=command_id,
            arguments=arguments,
            action_payload=arguments,
            risk_level=command["risk_level"],
            status=status_value,
            decided_at=timezone.now() if status_value == ApprovalRequest.Status.APPROVED else None,
            expires_at=timezone.now() + timedelta(minutes=30) if command["requires_approval"] else None,
        )
        return Response(ApprovalRequestSerializer(approval).data, status=status.HTTP_201_CREATED)


class ApprovalDecisionView(APIView):
    permission_classes = [IsAuthenticated]
    decision = ApprovalRequest.Status.APPROVED

    def post(self, request, pk):
        approval = generics.get_object_or_404(ApprovalRequest, pk=pk, owner=request.user)
        if approval.status != ApprovalRequest.Status.PENDING:
            return Response(
                {"message": "Ten approval request nie czeka juz na decyzje."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(ApprovalRequestSerializer(mark_decided(approval, self.decision)).data)


class ApprovalRejectView(ApprovalDecisionView):
    decision = ApprovalRequest.Status.REJECTED


class CliNextApprovalView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def get(self, request):
        device = request.auth
        queryset = ApprovalRequest.objects.filter(
            device=device,
            status=ApprovalRequest.Status.APPROVED,
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        queryset = queryset.order_by("requested_at")
        if connection.features.has_select_for_update:
            kwargs = {"skip_locked": connection.features.has_select_for_update_skip_locked}
            if connection.features.has_select_for_update_of:
                kwargs["of"] = ("self",)
            queryset = queryset.select_for_update(**kwargs)
        approval = queryset.first()
        if not approval:
            return Response(status=status.HTTP_204_NO_CONTENT)
        approval.status = ApprovalRequest.Status.RUNNING
        approval.started_at = timezone.now()
        approval.save(update_fields=["status", "started_at", "updated_at"])
        approval = ApprovalRequest.objects.select_related("project", "session", "task").get(pk=approval.pk)
        return Response(CliApprovalRequestSerializer(approval).data)


class CliFinishApprovalView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        approval = generics.get_object_or_404(ApprovalRequest, pk=pk, device=request.auth)
        serializer = ApprovalFinishSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        approval.status = data["status"]
        approval.result_message = data.get("result_message", "")
        approval.error_message = data.get("error_message", "")
        approval.stdout = data.get("stdout", "")
        approval.stderr = data.get("stderr", "")
        approval.exit_code = data.get("exit_code")
        approval.finished_at = timezone.now()
        approval.save(update_fields=["status", "result_message", "error_message", "stdout", "stderr", "exit_code", "finished_at", "updated_at"])
        if approval.status == ApprovalRequest.Status.SUCCEEDED and approval.session_id:
            branch = ""
            if approval.action_type in {"git.branch.switch", "git.branch.create"}:
                branch = str((approval.action_payload or {}).get("branch") or "").strip()
            if branch:
                approval.session.git_branch = branch
                approval.session.save(update_fields=["git_branch", "updated_at"])
            if approval.action_type == "codex.session.settings.update":
                serializer = SessionSettingsSerializer(approval.session, data=approval.arguments or {}, partial=True)
                serializer.allow_risky = True
                serializer.is_valid(raise_exception=True)
                serializer.save()
        return Response(CliApprovalRequestSerializer(approval).data)
