from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class TerminalSession(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        CLAIMED = "claimed", "Claimed"
        RUNNING = "running", "Running"
        EXITED = "exited", "Exited"
        KILLED = "killed", "Killed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="terminal_sessions")
    device = models.ForeignKey("devices.Device", on_delete=models.CASCADE, related_name="terminal_sessions")
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="terminal_sessions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    cwd = models.CharField(max_length=500)
    shell = models.CharField(max_length=40, default="pwsh")
    cols = models.PositiveIntegerField(default=96)
    rows = models.PositiveIntegerField(default=28)
    exit_code = models.IntegerField(null=True, blank=True)
    error_code = models.CharField(max_length=80, blank=True)
    error_message = models.TextField(blank=True)
    kill_requested = models.BooleanField(default=False)
    claimed_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    last_activity_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["owner", "-updated_at"], name="terminal_owner_updated_idx"),
            models.Index(fields=["device", "status", "created_at"], name="terminal_device_queue_idx"),
        ]

    @property
    def is_terminal(self) -> bool:
        return self.status in {self.Status.EXITED, self.Status.KILLED, self.Status.FAILED}


class TerminalEvent(models.Model):
    class Kind(models.TextChoices):
        READY = "ready", "Ready"
        STATUS = "status", "Status"
        OUTPUT = "output", "Output"
        STDERR = "stderr", "Stderr"
        CWD = "cwd", "Cwd"
        EXIT = "exit", "Exit"
        ERROR = "error", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(TerminalSession, on_delete=models.CASCADE, related_name="events")
    sequence = models.PositiveIntegerField()
    kind = models.CharField(max_length=20, choices=Kind.choices)
    stream = models.CharField(max_length=20, blank=True)
    data = models.TextField(blank=True)
    cwd = models.CharField(max_length=500, blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        indexes = [
            models.Index(fields=["session", "sequence"], name="terminal_event_sequence_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["session", "sequence"], name="unique_terminal_event_sequence")
        ]


class TerminalInput(models.Model):
    class Kind(models.TextChoices):
        STDIN = "stdin", "Stdin"
        RESIZE = "resize", "Resize"
        KILL = "kill", "Kill"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(TerminalSession, on_delete=models.CASCADE, related_name="inputs")
    sequence = models.PositiveIntegerField()
    kind = models.CharField(max_length=20, choices=Kind.choices)
    data = models.TextField(blank=True)
    cols = models.PositiveIntegerField(null=True, blank=True)
    rows = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence"]
        indexes = [
            models.Index(fields=["session", "sequence"], name="terminal_input_sequence_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["session", "sequence"], name="unique_terminal_input_sequence")
        ]

