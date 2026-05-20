from __future__ import annotations

import html
import json

from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.utils import timezone

from devices.models import Device
from projects.models import Project
from sessions.models import AgentSession, SessionMessage
from tasks.models import Task, TaskEvent

from .dev_logs import RECENT_ERRORS, RECENT_REQUESTS


def dev_logs_json(request):
    if not settings.DEBUG:
        raise Http404()
    return JsonResponse(
        {
            "now": timezone.now().isoformat(),
            "requests": list(RECENT_REQUESTS),
            "errors": list(RECENT_ERRORS),
        }
    )


def dev_panel(request):
    if not settings.DEBUG:
        raise Http404()

    devices = Device.objects.select_related("owner").order_by("-updated_at")[:20]
    projects = Project.objects.select_related("device", "owner").order_by("-updated_at")[:30]
    sessions = AgentSession.objects.select_related("owner", "device", "project").order_by("-updated_at")[:30]
    tasks = Task.objects.select_related("owner", "device", "project", "session").order_by("-updated_at")[:30]
    messages = SessionMessage.objects.select_related("session", "task").order_by("-created_at")[:40]
    events = TaskEvent.objects.select_related("task").order_by("-created_at")[:80]

    body = f"""
<!doctype html>
<html lang="pl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="3">
  <title>DevLink Debug Panel</title>
  <style>
    body {{ margin: 0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif; background: #f7f7f8; color: #111827; }}
    header {{ position: sticky; top: 0; z-index: 2; background: #0d0d0d; color: white; padding: 14px 18px; }}
    h1 {{ margin: 0; font-size: 20px; }}
    main {{ padding: 14px; display: grid; gap: 14px; }}
    section {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; overflow: hidden; }}
    h2 {{ margin: 0; padding: 10px 12px; font-size: 15px; border-bottom: 1px solid #e5e7eb; background: #fafafa; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
    th, td {{ padding: 7px 8px; border-bottom: 1px solid #eeeeee; text-align: left; vertical-align: top; }}
    th {{ color: #6b7280; font-weight: 700; background: #fcfcfc; }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 12px; white-space: pre-wrap; word-break: break-word; }}
    .ok {{ color: #047857; font-weight: 700; }}
    .bad {{ color: #b91c1c; font-weight: 700; }}
    .muted {{ color: #6b7280; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 14px; }}
  </style>
</head>
<body>
<header>
  <h1>DevLink Debug Panel</h1>
  <div class="muted">Auto-refresh co 3s. Teraz: {esc(timezone.now().isoformat())}</div>
</header>
<main>
  <section>
    <h2>Runtime</h2>
    <table>
      <tr><th>DEBUG</th><td>{settings.DEBUG}</td><th>ALLOWED_HOSTS</th><td><code>{esc(settings.ALLOWED_HOSTS)}</code></td></tr>
      <tr><th>ASGI</th><td><code>{esc(settings.ASGI_APPLICATION)}</code></td><th>Channel layer</th><td><code>{esc(settings.CHANNEL_LAYERS)}</code></td></tr>
      <tr><th>DB</th><td colspan="3"><code>{esc(settings.DATABASES['default'])}</code></td></tr>
    </table>
  </section>
  <div class="grid">
    <section><h2>Recent API requests</h2>{request_table()}</section>
    <section><h2>Recent API errors</h2>{error_table()}</section>
  </div>
  <div class="grid">
    <section><h2>Devices</h2>{devices_table(devices)}</section>
    <section><h2>Projects</h2>{projects_table(projects)}</section>
  </div>
  <section><h2>Sessions</h2>{sessions_table(sessions)}</section>
  <section><h2>Tasks</h2>{tasks_table(tasks)}</section>
  <section><h2>Session messages</h2>{messages_table(messages)}</section>
  <section><h2>Task events</h2>{events_table(events)}</section>
</main>
</body>
</html>
"""
    return HttpResponse(body)


def request_table() -> str:
    rows = "".join(
        f"<tr><td>{esc(item['method'])}</td><td><code>{esc(item['path'])}</code></td><td class='{status_class(item['status'])}'>{item['status']}</td><td>{item['duration_ms']}ms</td><td>{esc(item['remote_addr'])}</td><td>{esc(item['user'])}</td></tr>"
        for item in RECENT_REQUESTS
    )
    return table("<tr><th>Method</th><th>Path</th><th>Status</th><th>Time</th><th>IP</th><th>User</th></tr>", rows)


def error_table() -> str:
    rows = "".join(
        f"<tr><td>{esc(item['method'])}</td><td><code>{esc(item['path'])}</code></td><td class='bad'>{item['status']}</td><td>{esc(item['remote_addr'])}</td><td><pre>{esc(json.dumps(item['payload'], ensure_ascii=False, indent=2))}</pre></td></tr>"
        for item in RECENT_ERRORS
    )
    return table("<tr><th>Method</th><th>Path</th><th>Status</th><th>IP</th><th>Payload</th></tr>", rows)


def devices_table(devices) -> str:
    rows = "".join(
        f"<tr><td>{esc(device.name)}</td><td>{esc(device.owner.username)}</td><td>{esc(device.status)}</td><td>{esc(device.last_seen_at)}</td><td>{esc(device.capabilities_updated_at)}</td></tr>"
        for device in devices
    )
    return table("<tr><th>Name</th><th>Owner</th><th>Status</th><th>Last seen</th><th>Capabilities</th></tr>", rows)


def projects_table(projects) -> str:
    rows = "".join(
        f"<tr><td>{esc(project.name)}</td><td>{esc(project.owner.username)}</td><td>{esc(project.device.name)}</td><td>{project.is_active}</td><td><code>{esc(project.local_path)}</code></td></tr>"
        for project in projects
    )
    return table("<tr><th>Name</th><th>Owner</th><th>Device</th><th>Active</th><th>Path</th></tr>", rows)


def sessions_table(sessions) -> str:
    rows = "".join(
        f"<tr><td><code>{session.id}</code></td><td>{esc(session.owner.username)}</td><td>{esc(session.project.name)}</td><td class='{'' if session.status == 'open' else 'bad'}'>{esc(session.status)}</td><td>{esc(session.title)}</td><td>{esc(session.updated_at)}</td></tr>"
        for session in sessions
    )
    return table("<tr><th>ID</th><th>Owner</th><th>Project</th><th>Status</th><th>Title</th><th>Updated</th></tr>", rows)


def tasks_table(tasks) -> str:
    rows = "".join(
        f"<tr><td><code>{task.id}</code></td><td>{esc(task.owner.username)}</td><td>{esc(task.status)}</td><td>{esc(task.project.name)}</td><td>{esc(task.prompt[:180])}</td><td>{esc(task.error_code)} {esc(task.error_message)}</td><td>{esc(task.updated_at)}</td></tr>"
        for task in tasks
    )
    return table("<tr><th>ID</th><th>Owner</th><th>Status</th><th>Project</th><th>Prompt</th><th>Error</th><th>Updated</th></tr>", rows)


def messages_table(messages) -> str:
    rows = "".join(
        f"<tr><td>{esc(message.created_at)}</td><td>{esc(message.role)}</td><td><code>{esc(message.session_id)}</code></td><td><code>{esc(message.task_id or '')}</code></td><td>{esc(message.content[:220])}</td></tr>"
        for message in messages
    )
    return table("<tr><th>Created</th><th>Role</th><th>Session</th><th>Task</th><th>Content</th></tr>", rows)


def events_table(events) -> str:
    rows = "".join(
        f"<tr><td>{esc(event.created_at)}</td><td><code>{esc(event.task_id)}</code></td><td>{event.sequence}</td><td>{esc(event.event_type)}</td><td>{esc(event.message[:220])}</td><td><pre>{esc(json.dumps(event.payload, ensure_ascii=False, indent=2)[:1000])}</pre></td></tr>"
        for event in events
    )
    return table("<tr><th>Created</th><th>Task</th><th>Seq</th><th>Type</th><th>Message</th><th>Payload</th></tr>", rows)


def table(head: str, rows: str) -> str:
    return f"<table><thead>{head}</thead><tbody>{rows or '<tr><td class=\"muted\">Brak danych</td></tr>'}</tbody></table>"


def status_class(status: int) -> str:
    return "ok" if status < 400 else "bad"


def esc(value) -> str:
    return html.escape(str(value))
