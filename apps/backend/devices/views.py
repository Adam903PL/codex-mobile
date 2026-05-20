from django.utils import timezone
from django.db.models import Count, Q, Prefetch
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .auth import DeviceTokenAuthentication
from .models import Device
from agents.models import ApprovalRequest
from projects.models import Project
from sessions.models import AgentSession
from sessions.services import broadcast_session_capabilities_updated, broadcast_workspace_updated_for_device
from .serializers import (
    DeviceCapabilitiesSerializer,
    DeviceDetailSerializer,
    DeviceSerializer,
    PairDeviceSerializer,
    PairingCodeSerializer,
)
from .services import revoke_device


class PairingCodeCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PairingCodeSerializer


class PairDeviceView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PairDeviceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        payload = {
            "device": DeviceSerializer(result["device"]).data,
            "device_token": result["device_token"],
            "project_id": str(result["project"].id) if result["project"] else None,
        }
        return Response(payload, status=status.HTTP_201_CREATED)


class DeviceListView(generics.ListAPIView):
    serializer_class = DeviceSerializer
    pagination_class = None

    def get_queryset(self):
        return Device.objects.filter(owner=self.request.user).annotate(
            project_count=Count("projects", filter=Q(projects__is_active=True))
        )


class DeviceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = DeviceSerializer

    def get_serializer_class(self):
        if self.request.method == "GET":
            return DeviceDetailSerializer
        return DeviceSerializer

    def get_queryset(self):
        active_projects = Project.objects.filter(is_active=True).order_by("name")
        return (
            Device.objects.filter(owner=self.request.user)
            .annotate(project_count=Count("projects", filter=Q(projects__is_active=True)))
            .prefetch_related(Prefetch("projects", queryset=active_projects))
        )

    def perform_destroy(self, instance):
        revoke_device(instance)


class CliHeartbeatView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        device = request.auth
        device.status = Device.Status.BUSY if request.data.get("busy") else Device.Status.ONLINE
        device.last_seen_at = timezone.now()
        device.save(update_fields=["status", "last_seen_at", "updated_at"])
        return Response(DeviceSerializer(device).data)


class DeviceCapabilitiesView(generics.RetrieveAPIView):
    serializer_class = DeviceCapabilitiesSerializer

    def get_queryset(self):
        return Device.objects.filter(owner=self.request.user)


class DeviceCapabilitiesRefreshView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        device = generics.get_object_or_404(Device, pk=pk, owner=request.user)
        approval = ApprovalRequest.objects.create(
            owner=request.user,
            device=device,
            action_type="codex.capabilities.refresh",
            command_id="codex.capabilities.refresh",
            risk_level=ApprovalRequest.RiskLevel.LOW,
            status=ApprovalRequest.Status.APPROVED,
            decided_at=timezone.now(),
        )
        return Response({"id": str(approval.id), "status": approval.status}, status=status.HTTP_201_CREATED)


class CliCapabilitiesView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        device = request.auth
        device.capabilities = request.data
        device.capabilities_updated_at = timezone.now()
        device.save(update_fields=["capabilities", "capabilities_updated_at", "updated_at"])
        device_payload = DeviceCapabilitiesSerializer(device).data
        for session in AgentSession.objects.filter(device=device, status=AgentSession.Status.OPEN)[:20]:
            broadcast_session_capabilities_updated(session, device_payload)
        broadcast_workspace_updated_for_device(device, reason="capabilities.updated")
        return Response(device_payload)
