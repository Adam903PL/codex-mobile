from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class Task(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        CLAIMED = "claimed", "Claimed"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"
        TIMED_OUT = "timed_out", "Timed out"

    class AgentType(models.TextChoices):
        CODEX = "codex", "Codex"
        SHELL = "shell", "Shell"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tasks")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="tasks")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="tasks")
    session = models.ForeignKey(
        "agent_sessions.AgentSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    prompt = models.TextField()
    agent_type = models.CharField(max_length=40, choices=AgentType.choices, default=AgentType.CODEX)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    final_output = models.TextField(blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "-created_at"], name="task_owner_created_idx"),
            models.Index(fields=["owner", "status"], name="task_owner_status_idx"),
            models.Index(fields=["device", "status", "created_at"], name="task_queue_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.agent_type} task {self.id}"


class TaskEvent(models.Model):
    class EventType(models.TextChoices):
        STATUS = "status", "Status"
        STDOUT = "stdout", "Stdout"
        STDERR = "stderr", "Stderr"
        AGENT_EVENT = "agent_event", "Agent event"
        ERROR = "error", "Error"
        FINAL = "final", "Final"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="events")
    sequence = models.PositiveIntegerField()
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        indexes = [
            models.Index(fields=["task", "sequence"], name="task_event_sequence_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["task", "sequence"], name="unique_event_sequence_per_task")
        ]

    def __str__(self) -> str:
        return f"{self.task_id}#{self.sequence}:{self.event_type}"
