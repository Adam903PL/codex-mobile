from __future__ import annotations

import secrets
import string
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import serializers

from projects.models import Project

from .models import Device, PairingCode, hash_device_token

PAIRING_CODE_LENGTH = 6
PAIRING_CODE_TTL_MINUTES = 10


def _generate_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(alphabet) for _ in range(PAIRING_CODE_LENGTH))
    while PairingCode.objects.filter(code=code).exists():
        code = "".join(secrets.choice(alphabet) for _ in range(PAIRING_CODE_LENGTH))
    return code


@transaction.atomic
def create_pairing_code(owner) -> PairingCode:
    now = timezone.now()
    active_codes: QuerySet[PairingCode] = PairingCode.objects.filter(
        owner=owner,
        used_at__isnull=True,
        expires_at__gt=now,
    )
    active_codes.update(expires_at=now)
    return PairingCode.objects.create(
        owner=owner,
        code=_generate_code(),
        expires_at=now + timedelta(minutes=PAIRING_CODE_TTL_MINUTES),
    )


@transaction.atomic
def pair_device(
    *,
    code: str,
    name: str,
    platform: str = "",
    project_path: str = "",
    project_name: str = "",
) -> dict[str, Any]:
    normalized_code = code.upper()
    try:
        pairing_code = (
            PairingCode.objects.select_for_update()
            .select_related("owner")
            .get(code=normalized_code)
        )
    except PairingCode.DoesNotExist as exc:
        raise serializers.ValidationError({"code": ["Kod parowania nie istnieje."]}) from exc

    if not pairing_code.is_valid:
        raise serializers.ValidationError({"code": ["Kod parowania wygasl albo zostal juz uzyty."]})

    raw_token = secrets.token_urlsafe(40)
    device = Device.objects.create(
        owner=pairing_code.owner,
        name=name,
        platform=platform,
        status=Device.Status.ONLINE,
        token_hash=hash_device_token(raw_token),
        last_seen_at=timezone.now(),
    )

    project = None
    if project_path:
        project = Project.objects.create(
            owner=pairing_code.owner,
            device=device,
            name=project_name or project_path.replace("/", "\\").split("\\")[-1] or "DevLink Project",
            local_path=project_path,
        )

    pairing_code.mark_used()
    return {"device": device, "project": project, "device_token": raw_token}


def revoke_device(device: Device) -> Device:
    device.status = Device.Status.REVOKED
    device.save(update_fields=["status", "updated_at"])
    return device


def update_device_usage_limits(device: Device, usage_limits: dict[str, Any]) -> Device:
    if not isinstance(usage_limits, dict) or not usage_limits:
        return device
    capabilities = device.capabilities if isinstance(device.capabilities, dict) else {}
    diagnostics = capabilities.get("diagnostics") if isinstance(capabilities.get("diagnostics"), dict) else {}
    diagnostics = {
        **diagnostics,
        "usage_limits_source": usage_limits.get("source", ""),
        "usage_limits_probe_at": usage_limits.get("observed_at", ""),
    }
    device.capabilities = {
        **capabilities,
        "codex_usage_limits": usage_limits,
        "diagnostics": diagnostics,
    }
    device.capabilities_updated_at = timezone.now()
    device.save(update_fields=["capabilities", "capabilities_updated_at", "updated_at"])
    return device
