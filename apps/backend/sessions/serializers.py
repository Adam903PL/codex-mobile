from __future__ import annotations

from rest_framework import serializers

from projects.models import Project

from .models import AgentSession, SessionMessage

SAFE_SANDBOXES = {Project.SandboxMode.READ_ONLY, Project.SandboxMode.WORKSPACE_WRITE}
SAFE_APPROVAL_POLICIES = {Project.ApprovalPolicy.UNTRUSTED, Project.ApprovalPolicy.ON_REQUEST}
ALL_SANDBOXES = {
    Project.SandboxMode.READ_ONLY,
    Project.SandboxMode.WORKSPACE_WRITE,
    Project.SandboxMode.DANGER_FULL_ACCESS,
}
ALL_APPROVAL_POLICIES = {
    Project.ApprovalPolicy.UNTRUSTED,
    Project.ApprovalPolicy.ON_REQUEST,
    Project.ApprovalPolicy.NEVER,
}


class AgentSessionSerializer(serializers.ModelSerializer):
    device_name = serializers.CharField(source="device.name", read_only=True)
    device_status = serializers.CharField(source="device.status", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_path = serializers.CharField(source="project.local_path", read_only=True)
    parent_session_title = serializers.CharField(source="parent_session.title", read_only=True)
    task_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = AgentSession
        fields = [
            "id",
            "device",
            "device_name",
            "device_status",
            "project",
            "project_name",
            "project_path",
            "parent_session",
            "parent_session_title",
            "agent_type",
            "title",
            "summary",
            "codex_session_id",
            "model",
            "profile",
            "sandbox",
            "approval_policy",
            "git_branch",
            "add_dirs",
            "model_settings",
            "selected_skills",
            "web_search_enabled",
            "tool_settings",
            "status",
            "task_count",
            "last_activity_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class AgentSessionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentSession
        fields = [
            "id",
            "project",
            "agent_type",
            "title",
            "summary",
            "model",
            "profile",
            "sandbox",
            "approval_policy",
            "git_branch",
            "add_dirs",
            "model_settings",
            "selected_skills",
            "web_search_enabled",
            "tool_settings",
        ]
        read_only_fields = ["id"]

    def validate_project(self, project: Project) -> Project:
        request = self.context["request"]
        if project.owner != request.user:
            raise serializers.ValidationError("Nie masz dostepu do tego projektu.")
        if not project.is_active:
            raise serializers.ValidationError("Projekt jest nieaktywny.")
        if not project.device.is_available_for_tasks():
            raise serializers.ValidationError("Urzadzenie projektu nie jest polaczone. Uruchom devlink connect albo wybierz aktywny workspace.")
        return project

    def validate_sandbox(self, value: str) -> str:
        if value and value not in SAFE_SANDBOXES:
            raise serializers.ValidationError("Ten tryb sandboxa jest zablokowany do approval flow.")
        return value

    def validate_approval_policy(self, value: str) -> str:
        if value and value not in SAFE_APPROVAL_POLICIES:
            raise serializers.ValidationError("Ta polityka approval jest zablokowana do approval flow.")
        return value


class AgentSessionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentSession
        fields = ["title", "summary"]


class SessionSettingsSerializer(serializers.ModelSerializer):
    allow_risky = False

    class Meta:
        model = AgentSession
        fields = [
            "model",
            "profile",
            "sandbox",
            "approval_policy",
            "git_branch",
            "add_dirs",
            "model_settings",
            "selected_skills",
            "web_search_enabled",
            "tool_settings",
        ]

    def validate_sandbox(self, value: str) -> str:
        allowed = ALL_SANDBOXES if self.allow_risky else SAFE_SANDBOXES
        if value not in allowed:
            raise serializers.ValidationError("Ten tryb sandboxa jest zablokowany do approval flow.")
        return value

    def validate_approval_policy(self, value: str) -> str:
        allowed = ALL_APPROVAL_POLICIES if self.allow_risky else SAFE_APPROVAL_POLICIES
        if value not in allowed:
            raise serializers.ValidationError("Ta polityka approval jest zablokowana do approval flow.")
        return value

    def validate_selected_skills(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("selected_skills musi byc lista.")
        return [str(item) for item in value if str(item).strip()]

    def validate_add_dirs(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("add_dirs musi byc lista.")
        return [str(item) for item in value if str(item).strip()]

    def validate_model_settings(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("model_settings musi byc obiektem.")
        return value


class SessionMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionMessage
        fields = ["id", "session", "task", "role", "content", "status", "metadata", "created_at", "updated_at"]
        read_only_fields = fields


class SessionMessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField(allow_blank=False, trim_whitespace=True)
    settings_overrides = SessionSettingsSerializer(required=False)
    selected_skill_ids = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
    )
