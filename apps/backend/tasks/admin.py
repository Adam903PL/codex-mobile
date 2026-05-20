from django.contrib import admin

from .models import Task, TaskEvent


class TaskEventInline(admin.TabularInline):
    model = TaskEvent
    extra = 0
    can_delete = False
    readonly_fields = ["id", "sequence", "event_type", "message", "payload", "created_at"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ["id", "owner", "project", "device", "agent_type", "status", "created_at", "finished_at"]
    list_filter = ["status", "agent_type", "created_at", "finished_at"]
    search_fields = ["id", "prompt", "final_output", "error_code", "error_message", "owner__username", "project__name"]
    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "claimed_at",
        "started_at",
        "finished_at",
    ]
    inlines = [TaskEventInline]


@admin.register(TaskEvent)
class TaskEventAdmin(admin.ModelAdmin):
    list_display = ["task", "sequence", "event_type", "created_at"]
    list_filter = ["event_type", "created_at"]
    search_fields = ["task__id", "message"]
    readonly_fields = ["id", "task", "sequence", "event_type", "message", "payload", "created_at"]

