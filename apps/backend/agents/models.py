from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AgentKind(models.TextChoices):
    CODEX = "codex", "Codex"
    SHELL = "shell", "Shell"


class ApprovalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="approval_requests")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="approval_requests")
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="approval_requests",
        null=True,
        blank=True,
    )
    session = models.ForeignKey(
        "agent_sessions.AgentSession",
        on_delete=models.SET_NULL,
        related_name="approval_requests",
        null=True,
        blank=True,
    )
    task = models.ForeignKey(
        "tasks.Task",
        on_delete=models.SET_NULL,
        related_name="approval_requests",
        null=True,
        blank=True,
    )
    action_type = models.CharField(max_length=80)
    action_payload = models.JSONField(default=dict, blank=True)
    command_id = models.CharField(max_length=120, blank=True)
    arguments = models.JSONField(default=dict, blank=True)
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices, default=RiskLevel.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    result_message = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    requested_at = models.DateTimeField(default=timezone.now)
    decided_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at"]
        indexes = [
            models.Index(fields=["owner", "status", "-requested_at"], name="approval_owner_status_idx"),
            models.Index(fields=["device", "status", "requested_at"], name="approval_device_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action_type} approval {self.id}"
