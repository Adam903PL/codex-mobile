from __future__ import annotations

from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken

from .models import AgentSession
from .services import session_group_name


class SessionTimelineConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self) -> None:
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = session_group_name(self.session_id)
        token = self._token_from_query_string()
        self.user = await self._user_from_token(token)
        if not self.user or not await self._can_open_session(self.user.id, self.session_id):
            await self.close(code=4401)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connection.ready", "session": self.session_id})

    async def disconnect(self, code: int) -> None:
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def timeline_item(self, event: dict) -> None:
        await self.send_json({"type": "timeline.item", "item": event.get("item", {})})

    async def task_status(self, event: dict) -> None:
        await self.send_json({"type": "task.status", "task": event.get("task", {})})

    async def capabilities_updated(self, event: dict) -> None:
        await self.send_json({"type": "capabilities.updated", "device": event.get("device", {})})

    async def workspace_updated(self, event: dict) -> None:
        await self.send_json({"type": "workspace.updated", "payload": event.get("payload", {})})

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
    def _can_open_session(self, user_id: int, session_id: str) -> bool:
        return AgentSession.objects.filter(id=session_id, owner_id=user_id).exists()
