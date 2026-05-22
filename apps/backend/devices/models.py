from __future__ import annotations

import hashlib
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def hash_device_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


ACTIVE_HEARTBEAT_GRACE = timedelta(minutes=2)


class Device(models.Model):
    class Status(models.TextChoices):
        ONLINE = "online", "Online"
        OFFLINE = "offline", "Offline"
        BUSY = "busy", "Busy"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    name = models.CharField(max_length=120)
    platform = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OFFLINE)
    token_hash = models.CharField(max_length=64, unique=True)
    capabilities = models.JSONField(default=dict, blank=True)
    capabilities_updated_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def mark_seen(self, status: str = Status.ONLINE) -> None:
        self.status = status
        self.last_seen_at = timezone.now()
        self.save(update_fields=["status", "last_seen_at", "updated_at"])

    def is_available_for_tasks(self) -> bool:
        if self.status not in {self.Status.ONLINE, self.Status.BUSY} or not self.last_seen_at:
            return False
        return self.last_seen_at >= timezone.now() - ACTIVE_HEARTBEAT_GRACE

    def __str__(self) -> str:
        return f"{self.name} ({self.owner})"


class PairingCode(models.Model):
    code = models.CharField(max_length=12, unique=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pairing_codes")
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def is_valid(self) -> bool:
        return self.used_at is None and self.expires_at > timezone.now()

    def mark_used(self) -> None:
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])

    def __str__(self) -> str:
        return self.code
