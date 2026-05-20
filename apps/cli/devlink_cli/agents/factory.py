from __future__ import annotations

from .base import AgentAdapter
from .adapters.codex import CodexAdapter
from .adapters.shell import ShellAdapter


class AgentFactory:
    @staticmethod
    def create(agent_type: str) -> AgentAdapter:
        if agent_type == "codex":
            return CodexAdapter()
        if agent_type == "shell":
            return ShellAdapter()
        raise ValueError(f"Unsupported agent type: {agent_type}")

