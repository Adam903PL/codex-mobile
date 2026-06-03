from rest_framework import serializers

from .models import Project

ALLOWED_SANDBOXES = {Project.SandboxMode.READ_ONLY, Project.SandboxMode.WORKSPACE_WRITE}
ALLOWED_APPROVAL_POLICIES = {Project.ApprovalPolicy.UNTRUSTED, Project.ApprovalPolicy.ON_REQUEST}


class ProjectSettingsValidationMixin:
    def validate_default_sandbox(self, value: str) -> str:
        if value not in ALLOWED_SANDBOXES:
            raise serializers.ValidationError("Ten tryb sandboxa jest zablokowany do approval flow.")
        return value

    def validate_default_approval_policy(self, value: str) -> str:
        if value not in ALLOWED_APPROVAL_POLICIES:
            raise serializers.ValidationError("Ta polityka approval jest zablokowana do approval flow.")
        return value


class ProjectSerializer(ProjectSettingsValidationMixin, serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    device_status = serializers.CharField(source="device.status", read_only=True)
    device_last_seen_at = serializers.DateTimeField(source="device.last_seen_at", read_only=True)
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Project
        fields = [
            "id",
            "owner_username",
            "device",
            "device_name",
            "device_status",
            "device_last_seen_at",
            "name",
            "local_path",
            "repository_url",
            "default_model",
            "default_profile",
            "default_sandbox",
            "default_approval_policy",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner_username",
            "device",
            "device_name",
            "device_status",
            "device_last_seen_at",
            "local_path",
            "repository_url",
            "is_active",
            "created_at",
            "updated_at",
        ]


class CliProjectSerializer(ProjectSettingsValidationMixin, serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id",
            "name",
            "local_path",
            "repository_url",
            "default_model",
            "default_profile",
            "default_sandbox",
            "default_approval_policy",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_active", "created_at", "updated_at"]

    def validate_local_path(self, value: str) -> str:
        device = self.context["request"].auth
        queryset = Project.objects.filter(device=device, local_path=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Ten katalog jest juz zarejestrowany dla tego urzadzenia.")
        return value
