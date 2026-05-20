from __future__ import annotations

from django.utils import timezone
from rest_framework import serializers

from .models import ApprovalRequest


class ApprovalRequestSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    session_title = serializers.CharField(source="session.title", read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = [
            "id",
            "device",
            "device_name",
            "project",
            "project_name",
            "session",
            "session_title",
            "task",
            "action_type",
            "action_payload",
            "command_id",
            "arguments",
            "stdout",
            "stderr",
            "exit_code",
            "risk_level",
            "status",
            "result_message",
            "error_message",
            "requested_at",
            "decided_at",
            "started_at",
            "finished_at",
            "expires_at",
            "updated_at",
        ]
        read_only_fields = fields


class ApprovalRequestCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovalRequest
        fields = ["id", "device", "project", "session", "task", "action_type", "action_payload", "command_id", "arguments", "risk_level"]
        read_only_fields = ["id"]

    def validate(self, attrs):
        request = self.context["request"]
        for relation in ("device", "project", "session", "task"):
            value = attrs.get(relation)
            if value and value.owner_id != request.user.id:
                raise serializers.ValidationError({relation: ["Nie masz dostepu do tego zasobu."]})
        project = attrs.get("project")
        device = attrs.get("device")
        if project and device and project.device_id != device.id:
            raise serializers.ValidationError({"project": ["Projekt nie nalezy do wybranego urzadzenia."]})
        return attrs

    def create(self, validated_data):
        return ApprovalRequest.objects.create(owner=self.context["request"].user, **validated_data)


class CliApprovalRequestSerializer(serializers.ModelSerializer):
    project_path = serializers.CharField(source="project.local_path", read_only=True)

    class Meta:
        model = ApprovalRequest
        fields = [
            "id",
            "project",
            "project_path",
            "session",
            "task",
            "action_type",
            "action_payload",
            "command_id",
            "arguments",
            "risk_level",
            "status",
            "requested_at",
            "expires_at",
        ]


class ApprovalFinishSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[ApprovalRequest.Status.SUCCEEDED, ApprovalRequest.Status.FAILED])
    result_message = serializers.CharField(required=False, allow_blank=True)
    error_message = serializers.CharField(required=False, allow_blank=True)
    stdout = serializers.CharField(required=False, allow_blank=True)
    stderr = serializers.CharField(required=False, allow_blank=True)
    exit_code = serializers.IntegerField(required=False, allow_null=True)


def mark_decided(approval: ApprovalRequest, status_value: str) -> ApprovalRequest:
    approval.status = status_value
    approval.decided_at = timezone.now()
    approval.save(update_fields=["status", "decided_at", "updated_at"])
    return approval
