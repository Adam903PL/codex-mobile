from __future__ import annotations

from ..base import AgentEvent, AgentTask


class ShellAdapter:
    async def run(self, task: AgentTask):
        message = f"ShellAdapter testowy odebrał prompt dla projektu: {task.project_path}"
        yield AgentEvent(event_type="status", message="ShellAdapter test started")
        yield AgentEvent(event_type="stdout", message=message, payload={"prompt": task.prompt})
        yield AgentEvent(
            event_type="final",
            message=message,
            payload={"status": "succeeded", "exit_code": 0},
        )

