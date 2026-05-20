from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol


@dataclass(slots=True)
class AgentTask:
    id: str
    prompt: str
    project_path: str
    agent_type: str = "codex"
    model: str = ""
    profile: str = ""
    sandbox: str = "workspace-write"
    approval_policy: str = "on-request"
    git_branch: str = ""
    add_dirs: list[str] = field(default_factory=list)
    model_settings: dict[str, Any] = field(default_factory=dict)
    tool_settings: dict[str, Any] = field(default_factory=dict)
    images: list[str] = field(default_factory=list)
    session_id: str = ""
    codex_session_id: str = ""
    resume_mode: bool = False
    selected_skills: list[dict[str, Any]] = field(default_factory=list)
    web_search_enabled: bool = False
    cancel_event: asyncio.Event | None = field(default=None, repr=False)


@dataclass(slots=True)
class AgentEvent:
    event_type: str
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


class AgentAdapter(Protocol):
    async def run(self, task: AgentTask) -> AsyncIterator[AgentEvent]:
        ...


class AgentCanceled(RuntimeError):
    pass
