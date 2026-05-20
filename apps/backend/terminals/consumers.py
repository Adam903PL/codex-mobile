from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from .models import TerminalInput, TerminalSession
from .services import create_terminal_input, terminal_group_name


class TerminalConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        self.terminal_id = self.scope["url_route"]["kwargs"]["terminal_id"]
        self.group_name = terminal_group_name(self.terminal_id)
        token = self._token_from_query_string()
        self.user = await self._user_from_token(token)
        if not self.user or not await self._can_open_terminal(self.user.id, self.terminal_id):
            await self.close(code=4401)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "terminal.ready", "session": self.terminal_id})

    async def disconnect(self, code: int) -> None:
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content: dict, **kwargs) -> None:
        message_type = str(content.get("type") or "")
        if message_type == "stdin":
            await self._create_input(TerminalInput.Kind.STDIN, data=str(content.get("data") or ""))
        elif message_type == "resize":
            await self._create_input(
                TerminalInput.Kind.RESIZE,
                cols=int(content.get("cols") or 96),
                rows=int(content.get("rows") or 28),
            )
        elif message_type == "kill":
            await self._create_input(TerminalInput.Kind.KILL)

    async def terminal_event(self, event: dict) -> None:
        payload = event.get("event", {})
        kind = payload.get("kind") or "status"
        await self.send_json({"type": f"terminal.{kind}", "event": payload})

    def _token_from_query_string(self) -> str:
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        values = parse_qs(query_string).get("token") or []
        return values[0] if values else ""

    @database_sync_to_async
    def _user_from_token(self, token: str):
        if not token:
            return None
        try:
            payload = AccessToken(token)
            user_id = payload.get("user_id")
        except Exception:
            return None
        return get_user_model().objects.filter(id=user_id).first()

    @database_sync_to_async
    def _can_open_terminal(self, user_id: int, terminal_id: str) -> bool:
        return TerminalSession.objects.filter(id=terminal_id, owner_id=user_id).exists()

    @database_sync_to_async
    def _create_input(self, kind: str, data: str = "", cols: int | None = None, rows: int | None = None) -> None:
        terminal = TerminalSession.objects.get(id=self.terminal_id, owner=self.user)
        if terminal.is_terminal:
            return
        create_terminal_input(terminal, kind=kind, data=data, cols=cols, rows=rows)
