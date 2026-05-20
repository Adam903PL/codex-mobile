from datetime import timedelta

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.auth import DeviceTokenAuthentication
from agents.models import ApprovalRequest
from agents.serializers import ApprovalRequestSerializer
from sessions.models import AgentSession
from sessions.services import broadcast_workspace_updated_for_device

from .models import Project
from .serializers import CliProjectSerializer, ProjectSerializer


class ProjectListView(generics.ListAPIView):
    serializer_class = ProjectSerializer
    pagination_class = None

    def get_queryset(self):
        return Project.objects.select_related("device").filter(owner=self.request.user, is_active=True)


class ProjectDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ProjectSerializer

    def get_queryset(self):
        return Project.objects.select_related("device").filter(owner=self.request.user, is_active=True)


class CliProjectCreateView(generics.ListCreateAPIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = CliProjectSerializer
    pagination_class = None

    def get_queryset(self):
        return Project.objects.filter(device=self.request.auth, is_active=True)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user, device=self.request.auth)
        broadcast_workspace_updated_for_device(self.request.auth, reason="project.created")


class CliProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = CliProjectSerializer

    def get_queryset(self):
        return Project.objects.filter(device=self.request.auth, is_active=True)

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])


class ProjectGitBranchActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        project = generics.get_object_or_404(
            Project.objects.select_related("device"),
            pk=pk,
            owner=request.user,
            is_active=True,
        )
        action = str(request.data.get("action") or "switch").strip()
        branch = str(request.data.get("branch") or "").strip()
        base = str(request.data.get("base") or "").strip()
        dirty = bool(request.data.get("dirty", False))
        session_id = request.data.get("session")
        session = None
        if session_id:
            session = generics.get_object_or_404(
                AgentSession,
                pk=session_id,
                owner=request.user,
                project=project,
                status=AgentSession.Status.OPEN,
            )
        if action not in {"switch", "create"}:
            return Response({"message": "Nieznana akcja branch."}, status=status.HTTP_400_BAD_REQUEST)
        if not branch:
            return Response({"message": "Branch jest wymagany."}, status=status.HTTP_400_BAD_REQUEST)
        approval = ApprovalRequest.objects.create(
            owner=request.user,
            device=project.device,
            project=project,
            session=session,
            action_type=f"git.branch.{action}",
            action_payload={"branch": branch, "base": base, "dirty": dirty},
            risk_level=ApprovalRequest.RiskLevel.HIGH if dirty else ApprovalRequest.RiskLevel.MEDIUM,
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        return Response(ApprovalRequestSerializer(approval).data, status=status.HTTP_201_CREATED)
