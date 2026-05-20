from __future__ import annotations

import ntpath
import os
import posixpath
from typing import Any

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models import Max
from django.utils import timezone

from projects.models import Project

from .models import TerminalEvent, TerminalInput, TerminalSession


ACTIVE_STATUSES = {
    TerminalSession.Status.QUEUED,
    TerminalSession.Status.CLAIMED,
    TerminalSession.Status.RUNNING,
}


def normalize_terminal_cwd(project: Project, requested_cwd: str = "") -> str:
    root = project.local_path
    cwd = requested_cwd.strip() or root
    path_mod = ntpath if _looks_like_windows_path(root) or _looks_like_windows_path(cwd) else posixpath
    root_abs = path_mod.normcase(path_mod.abspath(path_mod.normpath(root)))
    cwd_abs = path_mod.normcase(path_mod.abspath(path_mod.normpath(cwd)))
    try:
        common = path_mod.commonpath([root_abs, cwd_abs])
    except ValueError as exc:
        raise ValueError("Terminal cwd must stay inside the registered workspace.") from exc
    if common != root_abs:
        raise ValueError("Terminal cwd must stay inside the registered workspace.")
    return cwd


def get_or_create_terminal_session(
    *,
    owner,
    project: Project,
    cwd: str = "",
    cols: int = 96,
    rows: int = 28,
) -> TerminalSession:
    cwd = normalize_terminal_cwd(project, cwd)
    existing = (
        TerminalSession.objects.filter(
            owner=owner,
            project=project,
            device=project.device,
            status__in=ACTIVE_STATUSES,
            kill_requested=False,
        )
        .order_by("-updated_at")
        .first()
    )
    if existing:
        return existing
    return TerminalSession.objects.create(
        owner=owner,
        device=project.device,
        project=project,
        cwd=cwd,
        cols=_clamp_dimension(cols, 20, 240),
        rows=_clamp_dimension(rows, 8, 80),
        last_activity_at=timezone.now(),
    )


def create_terminal_input(
    session: TerminalSession,
    *,
    kind: str,
    data: str = "",
    cols: int | None = None,
    rows: int | None = None,
) -> TerminalInput:
    next_sequence = (session.inputs.aggregate(max_sequence=Max("sequence"))["max_sequence"] or 0) + 1
    item = TerminalInput.objects.create(
        session=session,
        sequence=next_sequence,
        kind=kind,
        data=data,
        cols=cols,
        rows=rows,
    )
    session.last_activity_at = timezone.now()
    update_fields = ["last_activity_at", "updated_at"]
    if kind == TerminalInput.Kind.RESIZE:
        if cols:
            session.cols = _clamp_dimension(cols, 20, 240)
        if rows:
            session.rows = _clamp_dimension(rows, 8, 80)
        update_fields.extend(["cols", "rows"])
    if kind == TerminalInput.Kind.KILL:
        session.kill_requested = True
        update_fields.append("kill_requested")
    session.save(update_fields=update_fields)
    return item


def create_terminal_event(
    session: TerminalSession,
    *,
    kind: str,
    data: str = "",
    stream: str = "",
    cwd: str = "",
    exit_code: int | None = None,
    payload: dict[str, Any] | None = None,
) -> TerminalEvent:
    next_sequence = (session.events.aggregate(max_sequence=Max("sequence"))["max_sequence"] or 0) + 1
    event = TerminalEvent.objects.create(
        session=session,
        sequence=next_sequence,
        kind=kind,
        stream=stream,
        data=data,
        cwd=cwd,
        exit_code=exit_code,
        payload=payload or {},
    )
    _apply_event_to_session(session, event)
    broadcast_terminal_event(event)
    return event


def terminal_group_name(session_id: str) -> str:
    return f"terminal_{session_id}"


def broadcast_terminal_event(event: TerminalEvent) -> None:
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            terminal_group_name(str(event.session_id)),
            {"type": "terminal.event", "event": terminal_event_payload(event)},
        )
    except Exception:
        return


def terminal_event_payload(event: TerminalEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "session": str(event.session_id),
        "sequence": event.sequence,
        "kind": event.kind,
        "stream": event.stream,
        "data": event.data,
        "cwd": event.cwd,
        "exit_code": event.exit_code,
        "payload": event.payload,
        "created_at": event.created_at.isoformat(),
    }


def _apply_event_to_session(session: TerminalSession, event: TerminalEvent) -> None:
    now = timezone.now()
    update_fields = ["last_activity_at", "updated_at"]
    session.last_activity_at = now
    payload_status = str((event.payload or {}).get("status") or "").strip()
    if event.kind in {TerminalEvent.Kind.READY, TerminalEvent.Kind.STATUS} and payload_status:
        if payload_status in TerminalSession.Status.values:
            session.status = payload_status
            update_fields.append("status")
        if payload_status == TerminalSession.Status.RUNNING and not session.started_at:
            session.started_at = now
            update_fields.append("started_at")
    if event.kind == TerminalEvent.Kind.CWD and event.cwd:
        session.cwd = event.cwd
        update_fields.append("cwd")
    if event.kind == TerminalEvent.Kind.EXIT:
        session.status = TerminalSession.Status.KILLED if session.kill_requested else TerminalSession.Status.EXITED
        session.exit_code = event.exit_code
        session.finished_at = now
        update_fields.extend(["status", "exit_code", "finished_at"])
    if event.kind == TerminalEvent.Kind.ERROR:
        session.status = TerminalSession.Status.FAILED
        session.error_message = event.data
        session.error_code = str((event.payload or {}).get("error_code") or "TERMINAL_ERROR")
        session.finished_at = now
        update_fields.extend(["status", "error_message", "error_code", "finished_at"])
    session.save(update_fields=sorted(set(update_fields)))


def _looks_like_windows_path(value: str) -> bool:
    return "\\" in value or (len(value) >= 2 and value[1] == ":")


def _clamp_dimension(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, int(value or lower)))
