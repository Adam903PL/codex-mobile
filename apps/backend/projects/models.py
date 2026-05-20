from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Project(models.Model):
    class SandboxMode(models.TextChoices):
        READ_ONLY = "read-only", "Read only"
        WORKSPACE_WRITE = "workspace-write", "Workspace write"
        DANGER_FULL_ACCESS = "danger-full-access", "Danger full access"

    class ApprovalPolicy(models.TextChoices):
        UNTRUSTED = "untrusted", "Untrusted"
        ON_REQUEST = "on-request", "On request"
        NEVER = "never", "Never"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="projects")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=120)
    local_path = models.CharField(max_length=500)
    repository_url = models.URLField(blank=True)
    default_model = models.CharField(max_length=120, blank=True)
    default_profile = models.CharField(max_length=120, blank=True)
    default_sandbox = models.CharField(
        max_length=40,
        choices=SandboxMode.choices,
        default=SandboxMode.WORKSPACE_WRITE,
    )
    default_approval_policy = models.CharField(
        max_length=40,
        choices=ApprovalPolicy.choices,
        default=ApprovalPolicy.ON_REQUEST,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["device", "local_path"], name="unique_project_path_per_device")
        ]

    def __str__(self) -> str:
        return self.name
