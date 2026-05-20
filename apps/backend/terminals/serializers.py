from __future__ import annotations

from rest_framework import serializers

from .models import TerminalEvent, TerminalInput, TerminalSession


class TerminalSessionSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_path = serializers.CharField(source="project.local_path", read_only=True)

    class Meta:
        model = TerminalSession
        fields = [
            "id",
            "device",
            "device_name",
            "project",
            "project_name",
            "project_path",
            "status",
            "cwd",
            "shell",
            "cols",
            "rows",
            "exit_code",
            "error_code",
            "error_message",
            "kill_requested",
            "claimed_at",
            "started_at",
            "finished_at",
            "last_activity_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TerminalSessionCreateSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()
    cwd = serializers.CharField(required=False, allow_blank=True)
    cols = serializers.IntegerField(required=False, min_value=20, max_value=240, default=96)
    rows = serializers.IntegerField(required=False, min_value=8, max_value=80, default=28)


class TerminalEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TerminalEvent
        fields = ["id", "session", "sequence", "kind", "stream", "data", "cwd", "exit_code", "payload", "created_at"]
        read_only_fields = ["id", "session", "sequence", "created_at"]


class TerminalEventCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=TerminalEvent.Kind.choices)
    stream = serializers.CharField(required=False, allow_blank=True)
    data = serializers.CharField(required=False, allow_blank=True)
    cwd = serializers.CharField(required=False, allow_blank=True)
    exit_code = serializers.IntegerField(required=False, allow_null=True)
    payload = serializers.JSONField(required=False)


class TerminalInputSerializer(serializers.ModelSerializer):
    class Meta:
        model = TerminalInput
        fields = ["id", "session", "sequence", "kind", "data", "cols", "rows", "created_at"]
        read_only_fields = ["id", "session", "sequence", "created_at"]


class TerminalInputCreateSerializer(serializers.Serializer):
    data = serializers.CharField(allow_blank=True, default="")


class TerminalResizeSerializer(serializers.Serializer):
    cols = serializers.IntegerField(min_value=20, max_value=240)
    rows = serializers.IntegerField(min_value=8, max_value=80)
