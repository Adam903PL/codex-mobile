from django.contrib import admin

from .models import AgentSession, SessionMessage


@admin.register(AgentSession)
class AgentSessionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "title",
        "owner",
        "device",
        "project",
        "agent_type",
        "status",
        "model",
        "sandbox",
        "codex_session_id",
        "last_activity_at",
        "created_at",
    ]
    list_filter = ["agent_type", "status", "sandbox", "approval_policy", "web_search_enabled", "created_at", "updated_at"]
    search_fields = ["id", "title", "codex_session_id", "owner__username", "device__name", "project__name"]
    readonly_fields = ["id", "codex_session_id", "last_activity_at", "created_at", "updated_at"]


@admin.register(SessionMessage)
class SessionMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "task", "role", "status", "created_at"]
    list_filter = ["role", "status", "created_at"]
    search_fields = ["id", "session__title", "content"]
    readonly_fields = ["id", "created_at", "updated_at"]
