from __future__ import annotations

from rest_framework import serializers

from projects.models import Project
from sessions.models import AgentSession
from sessions.services import touch_session

from .models import Task, TaskEvent
from .services import create_task_event


class TaskEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TaskEvent
        fields = ["id", "sequence", "event_type", "message", "payload", "created_at"]
        read_only_fields = ["id", "sequence", "created_at"]

    def create(self, validated_data):
        task = self.context["task"]
        return create_task_event(task=task, **validated_data)


class TaskSerializer(serializers.ModelSerializer):
    project_name = serializers.CharField(source="project.name", read_only=True)
    device_name = serializers.CharField(source="device.name", read_only=True)
    session_title = serializers.CharField(source="session.title", read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "device",
            "device_name",
            "project",
            "project_name",
            "session",
            "session_title",
            "prompt",
            "agent_type",
            "status",
            "final_output",
            "exit_code",
            "error_code",
            "error_message",
            "claimed_at",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "device",
            "device_name",
            "project_name",
            "session_title",
            "status",
            "final_output",
            "exit_code",
            "error_code",
            "error_message",
            "claimed_at",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]


class TaskCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "project", "session", "prompt", "agent_type", "status", "created_at"]
        read_only_fields = ["id", "status", "created_at"]

    def validate_project(self, project: Project):
        if project.owner != self.context["request"].user:
            raise serializers.ValidationError("Nie masz dostepu do tego projektu.")
        if not project.is_active:
            raise serializers.ValidationError("Projekt jest nieaktywny.")
        if project.device.status == "revoked":
            raise serializers.ValidationError("Urzadzenie projektu zostalo odlaczone.")
        return project

    def validate(self, attrs):
        session = attrs.get("session")
        project = attrs.get("project")
        if session and session.owner != self.context["request"].user:
            raise serializers.ValidationError("Nie masz dostepu do tej sesji.")
        if session and project and session.project_id != project.id:
            raise serializers.ValidationError("Sesja musi nalezec do wybranego projektu.")
        if session and session.status == AgentSession.Status.CLOSED:
            raise serializers.ValidationError("Sesja jest zamknieta i nie moze przyjmowac nowych zadan.")
        agent_type = attrs.get("agent_type", Task.AgentType.CODEX)
        if session and session.agent_type != agent_type:
            raise serializers.ValidationError("Typ agenta zadania musi byc zgodny z sesja.")
        return attrs

    def create(self, validated_data):
        project = validated_data["project"]
        task = Task.objects.create(
            owner=self.context["request"].user,
            device=project.device,
            **validated_data,
        )
        touch_session(task.session)
        return task


class ClaimedTaskSerializer(serializers.ModelSerializer):
    project_path = serializers.CharField(source="project.local_path", read_only=True)
    default_model = serializers.SerializerMethodField()
    default_profile = serializers.SerializerMethodField()
    default_sandbox = serializers.SerializerMethodField()
    default_approval_policy = serializers.SerializerMethodField()
    git_branch = serializers.SerializerMethodField()
    add_dirs = serializers.SerializerMethodField()
    model_settings = serializers.SerializerMethodField()
    tool_settings = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    codex_session_id = serializers.CharField(source="session.codex_session_id", read_only=True)
    parent_session = serializers.UUIDField(source="session.parent_session_id", read_only=True)
    resume_mode = serializers.SerializerMethodField()
    selected_skills = serializers.SerializerMethodField()
    web_search_enabled = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            "id",
            "prompt",
            "agent_type",
            "project",
            "project_path",
            "session",
            "codex_session_id",
            "parent_session",
            "resume_mode",
            "status",
            "created_at",
            "default_model",
            "default_profile",
            "default_sandbox",
            "default_approval_policy",
            "git_branch",
            "add_dirs",
            "model_settings",
            "tool_settings",
            "images",
            "selected_skills",
            "web_search_enabled",
        ]

    def get_resume_mode(self, task: Task) -> bool:
        return bool(task.session_id and task.session and task.session.codex_session_id)

    def get_default_model(self, task: Task) -> str:
        return task.session.model if task.session_id and task.session and task.session.model else task.project.default_model

    def get_default_profile(self, task: Task) -> str:
        return task.session.profile if task.session_id and task.session and task.session.profile else task.project.default_profile

    def get_default_sandbox(self, task: Task) -> str:
        return task.session.sandbox if task.session_id and task.session and task.session.sandbox else task.project.default_sandbox

    def get_default_approval_policy(self, task: Task) -> str:
        if task.session_id and task.session and task.session.approval_policy:
            return task.session.approval_policy
        return task.project.default_approval_policy

    def get_git_branch(self, task: Task) -> str:
        return task.session.git_branch if task.session_id and task.session and task.session.git_branch else ""

    def get_add_dirs(self, task: Task) -> list[str]:
        return task.session.add_dirs if task.session_id and task.session and isinstance(task.session.add_dirs, list) else []

    def get_model_settings(self, task: Task) -> dict:
        return (
            task.session.model_settings
            if task.session_id and task.session and isinstance(task.session.model_settings, dict)
            else {}
        )

    def get_tool_settings(self, task: Task) -> dict:
        return (
            task.session.tool_settings
            if task.session_id and task.session and isinstance(task.session.tool_settings, dict)
            else {}
        )

    def get_images(self, task: Task) -> list[str]:
        if not task.session_id or not task.session or not isinstance(task.session.tool_settings, dict):
            return []
        images = task.session.tool_settings.get("images") or []
        if isinstance(images, str):
            return [images]
        if isinstance(images, list):
            return [str(image) for image in images if str(image).strip()]
        return []

    def get_web_search_enabled(self, task: Task) -> bool:
        return bool(task.session_id and task.session and task.session.web_search_enabled)

    def get_selected_skills(self, task: Task) -> list[dict]:
        if not task.session_id or not task.session:
            return []
        selected_ids = {str(skill_id) for skill_id in task.session.selected_skills}
        if not selected_ids:
            return []
        skills = task.device.capabilities.get("skills", []) if isinstance(task.device.capabilities, dict) else []
        return [skill for skill in skills if str(skill.get("id")) in selected_ids]


class CliTaskStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = ["id", "status", "updated_at"]


class FinishTaskSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[Task.Status.SUCCEEDED, Task.Status.FAILED, Task.Status.TIMED_OUT])
    final_output = serializers.CharField(required=False, allow_blank=True)
    exit_code = serializers.IntegerField(required=False, allow_null=True)
    error_code = serializers.CharField(required=False, allow_blank=True)
    error_message = serializers.CharField(required=False, allow_blank=True)
