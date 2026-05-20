from __future__ import annotations

from django.db import connection, transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from devices.auth import DeviceTokenAuthentication
from projects.models import Project

from .models import TerminalEvent, TerminalInput, TerminalSession
from .serializers import (
    TerminalEventCreateSerializer,
    TerminalEventSerializer,
    TerminalInputCreateSerializer,
    TerminalInputSerializer,
    TerminalResizeSerializer,
    TerminalSessionCreateSerializer,
    TerminalSessionSerializer,
)
from .services import create_terminal_event, create_terminal_input, get_or_create_terminal_session


class TerminalSessionCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = TerminalSessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = generics.get_object_or_404(
            Project.objects.select_related("device"),
            pk=serializer.validated_data["project_id"],
            owner=request.user,
            is_active=True,
        )
        try:
            terminal = get_or_create_terminal_session(
                owner=request.user,
                project=project,
                cwd=serializer.validated_data.get("cwd", ""),
                cols=serializer.validated_data.get("cols", 96),
                rows=serializer.validated_data.get("rows", 28),
            )
        except ValueError as exc:
            return Response({"message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TerminalSessionSerializer(terminal).data, status=status.HTTP_201_CREATED)


class TerminalSessionDetailView(generics.RetrieveAPIView):
    serializer_class = TerminalSessionSerializer

    def get_queryset(self):
        return TerminalSession.objects.select_related("device", "project").filter(owner=self.request.user)


class TerminalEventListView(generics.ListAPIView):
    serializer_class = TerminalEventSerializer
    pagination_class = None

    def get_queryset(self):
        terminal = generics.get_object_or_404(TerminalSession, pk=self.kwargs["pk"], owner=self.request.user)
        queryset = terminal.events.all()
        after = self.request.query_params.get("after")
        if after and after.isdigit():
            queryset = queryset.filter(sequence__gt=int(after))
        return queryset


class TerminalInputView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        terminal = generics.get_object_or_404(TerminalSession, pk=pk, owner=request.user)
        if terminal.is_terminal:
            return Response({"message": "Terminal session already finished."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = TerminalInputCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = create_terminal_input(
            terminal,
            kind=TerminalInput.Kind.STDIN,
            data=serializer.validated_data.get("data", ""),
        )
        return Response(TerminalInputSerializer(item).data, status=status.HTTP_201_CREATED)


class TerminalResizeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        terminal = generics.get_object_or_404(TerminalSession, pk=pk, owner=request.user)
        if terminal.is_terminal:
            return Response({"message": "Terminal session already finished."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = TerminalResizeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = create_terminal_input(
            terminal,
            kind=TerminalInput.Kind.RESIZE,
            cols=serializer.validated_data["cols"],
            rows=serializer.validated_data["rows"],
        )
        return Response(TerminalInputSerializer(item).data, status=status.HTTP_201_CREATED)


class TerminalKillView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        terminal = generics.get_object_or_404(TerminalSession, pk=pk, owner=request.user)
        if terminal.is_terminal:
            return Response(TerminalSessionSerializer(terminal).data)
        if terminal.status == TerminalSession.Status.QUEUED:
            terminal.kill_requested = True
            terminal.status = TerminalSession.Status.KILLED
            terminal.finished_at = timezone.now()
            terminal.last_activity_at = terminal.finished_at
            terminal.save(update_fields=["kill_requested", "status", "finished_at", "last_activity_at", "updated_at"])
            create_terminal_event(
                terminal,
                kind=TerminalEvent.Kind.STATUS,
                data="Terminal killed before local CLI claimed it",
                payload={"status": terminal.status, "kill_requested": True},
            )
            return Response(TerminalSessionSerializer(terminal).data)
        create_terminal_input(terminal, kind=TerminalInput.Kind.KILL)
        terminal.kill_requested = True
        terminal.save(update_fields=["kill_requested", "updated_at"])
        create_terminal_event(
            terminal,
            kind=TerminalEvent.Kind.STATUS,
            data="Kill requested",
            payload={"status": terminal.status, "kill_requested": True},
        )
        return Response(TerminalSessionSerializer(terminal).data)


class CliNextTerminalSessionView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def get(self, request):
        device = request.auth
        queryset = (
            TerminalSession.objects.select_related("project", "device")
            .filter(device=device, status=TerminalSession.Status.QUEUED, kill_requested=False)
        )
        if connection.features.has_select_for_update:
            queryset = queryset.select_for_update(skip_locked=connection.features.has_select_for_update_skip_locked)
        terminal = queryset.order_by("created_at").first()
        if not terminal:
            return Response(status=status.HTTP_204_NO_CONTENT)
        terminal.status = TerminalSession.Status.CLAIMED
        terminal.claimed_at = timezone.now()
        terminal.last_activity_at = terminal.claimed_at
        terminal.save(update_fields=["status", "claimed_at", "last_activity_at", "updated_at"])
        create_terminal_event(
            terminal,
            kind=TerminalEvent.Kind.STATUS,
            data="Terminal claimed",
            payload={"status": terminal.status},
        )
        return Response(TerminalSessionSerializer(terminal).data)


class CliTerminalInputListView(generics.ListAPIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = TerminalInputSerializer
    pagination_class = None

    def get_queryset(self):
        terminal = generics.get_object_or_404(TerminalSession, pk=self.kwargs["pk"], device=self.request.auth)
        queryset = terminal.inputs.all()
        after = self.request.query_params.get("after")
        if after and after.isdigit():
            queryset = queryset.filter(sequence__gt=int(after))
        return queryset


class CliTerminalEventCreateView(APIView):
    authentication_classes = [DeviceTokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        terminal = generics.get_object_or_404(TerminalSession, pk=pk, device=request.auth)
        serializer = TerminalEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        event = create_terminal_event(terminal, **serializer.validated_data)
        return Response(TerminalEventSerializer(event).data, status=status.HTTP_201_CREATED)
