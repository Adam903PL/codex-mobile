from __future__ import annotations

from typing import Any

from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import AgentSession, SessionMessage


SESSION_ID_KEYS = ("codex_session_id", "thread_id", "session_id", "conversation_id")


def touch_session(session: AgentSession | None) -> None:
    if not session:
        return
    session.last_activity_at = timezone.now()
    session.save(update_fields=["last_activity_at", "updated_at"])


def update_codex_session_from_payload(session: AgentSession | None, payload: dict[str, Any]) -> None:
    if not session:
        return
    codex_session_id = extract_codex_session_id(payload)
    if not _is_valid_codex_session_id(codex_session_id) or codex_session_id == session.codex_session_id:
        return
    session.codex_session_id = codex_session_id
    session.last_activity_at = timezone.now()
    session.save(update_fields=["codex_session_id", "last_activity_at", "updated_at"])


def session_group_name(session_id: str) -> str:
    return f"session_{session_id}"


def broadcast_session_timeline(session: AgentSession | None, item: dict[str, Any]) -> None:
    if not session:
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            session_group_name(str(session.id)),
            {"type": "timeline.item", "item": item},
        )
    except Exception:
        # Realtime is best-effort; REST timeline remains the fallback.
        return


def broadcast_session_task_status(session: AgentSession | None, task: dict[str, Any]) -> None:
    if not session:
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            session_group_name(str(session.id)),
            {"type": "task.status", "task": task},
        )
    except Exception:
        return


def broadcast_session_capabilities_updated(session: AgentSession | None, device: dict[str, Any]) -> None:
    if not session:
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            session_group_name(str(session.id)),
            {"type": "capabilities.updated", "device": device},
        )
    except Exception:
        return


def broadcast_session_workspace_updated(session: AgentSession | None, payload: dict[str, Any]) -> None:
    if not session:
        return
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            session_group_name(str(session.id)),
            {"type": "workspace.updated", "payload": payload},
        )
    except Exception:
        return


def broadcast_workspace_updated_for_device(device, reason: str = "workspace.updated") -> None:
    payload = {
        "reason": reason,
        "device_id": str(device.id),
        "device_name": device.name,
        "owner_id": device.owner_id,
        "owner_username": getattr(device.owner, "username", ""),
    }
    sessions = AgentSession.objects.filter(
        owner_id=device.owner_id,
        status=AgentSession.Status.OPEN,
    ).select_related("device")[:50]
    for session in sessions:
        broadcast_session_workspace_updated(session, payload)


def create_assistant_message_for_task(task) -> SessionMessage | None:
    if not task.session_id:
        return None
    existing = SessionMessage.objects.filter(
        session=task.session,
        task=task,
        role=SessionMessage.Role.ASSISTANT,
    ).first()
    if existing:
        return existing
    status = SessionMessage.Status.COMPLETE if task.status == "succeeded" else SessionMessage.Status.ERROR
    content = task.final_output or task.error_message or task.error_code or f"Task finished with status {task.status}."
    message = SessionMessage.objects.create(
        session=task.session,
        task=task,
        role=SessionMessage.Role.ASSISTANT,
        content=content,
        status=status,
        metadata={
            "task_status": task.status,
            "exit_code": task.exit_code,
            "error_code": task.error_code,
        },
    )
    broadcast_session_timeline(task.session, timeline_item_for_message(message))
    return message


def timeline_item_for_message(message: SessionMessage) -> dict[str, Any]:
    kind = "assistant_message"
    if message.role == SessionMessage.Role.USER:
        kind = "user_message"
    elif message.role == SessionMessage.Role.SYSTEM:
        kind = "status"
    return {
        "kind": kind,
        "id": str(message.id),
        "message_id": str(message.id),
        "task_id": str(message.task_id) if message.task_id else None,
        "sequence": 0,
        "content": message.content,
        "payload": message.metadata,
        "created_at": message.created_at.isoformat(),
    }


def timeline_item_for_event(event) -> dict[str, Any]:
    kind = "status"
    payload = event.payload if isinstance(event.payload, dict) else {}
    explicit_kind = str(payload.get("kind") or "").strip()
    if explicit_kind:
        kind = explicit_kind
    elif event.event_type == "stdout":
        kind = "terminal_stdout"
    elif event.event_type == "stderr":
        kind = "warning" if payload.get("level") == "warning" else "terminal_stderr"
    elif event.event_type == "error":
        kind = "error"
    elif event.event_type == "final":
        kind = "final"
    elif event.event_type == "status":
        status_value = str(payload.get("to") or payload.get("status") or "").lower()
        if status_value == "queued":
            kind = "queued"
        elif status_value in {"claimed", "running"}:
            kind = "running"
        elif status_value in {"succeeded", "failed", "canceled", "timed_out"}:
            kind = "status"
    elif event.event_type == "agent_event":
        kind = classify_agent_event(payload)
    payload = {"source": "backend", **payload}
    return {
        "kind": kind,
        "id": str(event.id),
        "event_id": str(event.id),
        "task_id": str(event.task_id),
        "sequence": event.sequence,
        "content": event.message,
        "payload": payload,
        "created_at": event.created_at.isoformat(),
    }


def classify_agent_event(payload: dict[str, Any]) -> str:
    explicit_kind = str(payload.get("kind") or "").strip()
    if explicit_kind:
        return explicit_kind
    event_name = str(payload.get("type") or payload.get("event") or payload.get("name") or "").lower()
    if "reason" in event_name or "thinking" in event_name:
        return "reasoning_summary"
    if "command" in event_name or "tool" in event_name or "exec" in event_name:
        return "tool_call"
    if "diff" in event_name or "patch" in event_name or "file" in event_name:
        return "diff"
    if "error" in event_name or "failed" in event_name:
        return "error"
    return "status"


def extract_codex_session_id(value: Any) -> str:
    if not isinstance(value, dict):
        return ""

    direct = _first_direct_session_id(value)
    if direct:
        return direct

    event_name = str(value.get("type") or value.get("event") or value.get("name") or "").lower()
    if ("thread" in event_name or "session" in event_name) and isinstance(value.get("id"), str):
        return value["id"]

    for nested_key in ("item", "data", "payload", "thread", "session", "conversation"):
        nested = value.get(nested_key)
        nested_id = _extract_nested_session_id(nested)
        if nested_id:
            return nested_id
    return ""


def _first_direct_session_id(value: dict[str, Any]) -> str:
    for key in SESSION_ID_KEYS:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return ""


def _extract_nested_session_id(value: Any) -> str:
    if isinstance(value, dict):
        direct = _first_direct_session_id(value)
        if direct:
            return direct
        for nested in value.values():
            nested_id = _extract_nested_session_id(nested)
            if nested_id:
                return nested_id
    if isinstance(value, list):
        for item in value:
            nested_id = _extract_nested_session_id(item)
            if nested_id:
                return nested_id
    return ""


def _is_valid_codex_session_id(value: str) -> bool:
    if not value:
        return False
    # Codex item ids identify individual output items, not resumable threads.
    return not value.startswith("item_")
