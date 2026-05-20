from __future__ import annotations

from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from devices.services import update_device_usage_limits
from sessions.services import (
    broadcast_session_capabilities_updated,
    broadcast_session_timeline,
    broadcast_session_task_status,
    timeline_item_for_event,
    touch_session,
    update_codex_session_from_payload,
)

from .models import Task, TaskEvent

TERMINAL_STATUSES = {
    Task.Status.SUCCEEDED,
    Task.Status.FAILED,
    Task.Status.CANCELED,
    Task.Status.TIMED_OUT,
}

ALLOWED_STATUS_TRANSITIONS = {
    Task.Status.QUEUED: {Task.Status.CLAIMED, Task.Status.CANCELED},
    Task.Status.CLAIMED: {Task.Status.RUNNING, Task.Status.CANCELED},
    Task.Status.RUNNING: {
        Task.Status.SUCCEEDED,
        Task.Status.FAILED,
        Task.Status.CANCELED,
        Task.Status.TIMED_OUT,
    },
    Task.Status.SUCCEEDED: set(),
    Task.Status.FAILED: set(),
    Task.Status.CANCELED: set(),
    Task.Status.TIMED_OUT: set(),
}


def validate_status_transition(current_status: str, target_status: str) -> None:
    allowed_targets = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if target_status not in allowed_targets:
        raise ValidationError(
            {
                "status": (
                    f"Invalid task status transition: {current_status} -> {target_status}."
                )
            }
        )


def create_task_event(
    task: Task,
    event_type: str,
    message: str = "",
    payload: dict | None = None,
) -> TaskEvent:
    with transaction.atomic():
        locked_task = Task.objects.select_for_update().get(pk=task.pk)
        event = _create_task_event(locked_task, event_type, message, payload or {})
        touch_session(locked_task.session)
        if isinstance(event.payload, dict):
            update_codex_session_from_payload(locked_task.session, event.payload)
            update_usage_limits_from_event(locked_task, event.payload)
        broadcast_session_timeline(locked_task.session, timeline_item_for_event(event))
        return event


def transition_task(
    task: Task,
    target_status: str,
    message: str = "",
    event_payload: dict | None = None,
    **fields,
) -> Task:
    with transaction.atomic():
        locked_task = Task.objects.select_for_update().get(pk=task.pk)
        previous_status = locked_task.status
        validate_status_transition(previous_status, target_status)

        now = timezone.now()
        locked_task.status = target_status
        update_fields = {"status", "updated_at"}

        if target_status == Task.Status.CLAIMED and locked_task.claimed_at is None:
            locked_task.claimed_at = now
            update_fields.add("claimed_at")
        if target_status == Task.Status.RUNNING and locked_task.started_at is None:
            locked_task.started_at = now
            update_fields.add("started_at")
        if target_status in TERMINAL_STATUSES and locked_task.finished_at is None:
            locked_task.finished_at = now
            update_fields.add("finished_at")

        for field_name, field_value in fields.items():
            setattr(locked_task, field_name, field_value)
            update_fields.add(field_name)

        locked_task.save(update_fields=sorted(update_fields))
        event = _create_task_event(
            locked_task,
            TaskEvent.EventType.STATUS,
            message or f"Task status changed to {target_status}",
            {
                "from": previous_status,
                "to": target_status,
                **(event_payload or {}),
            },
        )
        touch_session(locked_task.session)
        broadcast_session_timeline(locked_task.session, timeline_item_for_event(event))
        broadcast_session_task_status(
            locked_task.session,
            {
                "id": str(locked_task.id),
                "status": locked_task.status,
                "updated_at": locked_task.updated_at.isoformat(),
            },
        )
        return locked_task


def _create_task_event(task: Task, event_type: str, message: str, payload: dict) -> TaskEvent:
    next_sequence = (task.events.aggregate(max_sequence=Max("sequence"))["max_sequence"] or 0) + 1
    return TaskEvent.objects.create(
        task=task,
        sequence=next_sequence,
        event_type=event_type,
        message=message,
        payload=payload,
    )


def update_usage_limits_from_event(task: Task, payload: dict) -> None:
    usage_limits = payload.get("codex_usage_limits")
    if not isinstance(usage_limits, dict) or not usage_limits:
        return
    device = update_device_usage_limits(task.device, usage_limits)

    from devices.serializers import DeviceCapabilitiesSerializer
    from sessions.models import AgentSession

    device_payload = DeviceCapabilitiesSerializer(device).data
    for session in AgentSession.objects.filter(device=device, status=AgentSession.Status.OPEN)[:20]:
        broadcast_session_capabilities_updated(session, device_payload)
