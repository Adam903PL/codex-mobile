from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AgentSession(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="agent_sessions")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="agent_sessions")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="agent_sessions")
    parent_session = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="forks",
    )
    agent_type = models.CharField(max_length=40, default="codex")
    title = models.CharField(max_length=160, blank=True)
    summary = models.TextField(blank=True)
    codex_session_id = models.CharField(max_length=160, blank=True)
    model = models.CharField(max_length=120, blank=True)
    profile = models.CharField(max_length=120, blank=True)
    sandbox = models.CharField(max_length=40, default="workspace-write")
    approval_policy = models.CharField(max_length=40, default="on-request")
    git_branch = models.CharField(max_length=160, blank=True)
    add_dirs = models.JSONField(default=list, blank=True)
    model_settings = models.JSONField(default=dict, blank=True)
    selected_skills = models.JSONField(default=list, blank=True)
    web_search_enabled = models.BooleanField(default=False)
    tool_settings = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at", "-created_at"]
        indexes = [
            models.Index(fields=["owner", "project", "status", "-updated_at"], name="session_owner_project_idx"),
            models.Index(fields=["codex_session_id"], name="session_codex_id_idx"),
        ]

    def __str__(self) -> str:
        label = self.title or f"{self.agent_type} session"
        return f"{label} for {self.project}"


class SessionMessage(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        RUNNING = "running", "Running"
        COMPLETE = "complete", "Complete"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(AgentSession, on_delete=models.CASCADE, related_name="messages")
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["session", "created_at"], name="session_message_time_idx"),
            models.Index(fields=["task", "role"], name="session_message_task_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.role} message in {self.session_id}"
