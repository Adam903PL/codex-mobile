from django.contrib import admin

from .models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "owner",
        "device",
        "is_active",
        "default_sandbox",
        "default_approval_policy",
        "updated_at",
    ]
    list_filter = ["is_active", "default_sandbox", "default_approval_policy", "created_at", "updated_at"]
    search_fields = [
        "name",
        "local_path",
        "repository_url",
        "default_model",
        "default_profile",
        "owner__username",
        "device__name",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
