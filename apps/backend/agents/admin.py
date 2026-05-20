from django.contrib import admin

from .models import ApprovalRequest


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ["id", "action_type", "owner", "device", "project", "risk_level", "status", "requested_at"]
    list_filter = ["action_type", "risk_level", "status", "requested_at", "updated_at"]
    search_fields = ["id", "owner__username", "device__name", "project__name", "action_type"]
    readonly_fields = ["id", "requested_at", "decided_at", "updated_at"]
