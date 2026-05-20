from django.contrib import admin

from .models import Device, PairingCode


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ["name", "owner", "platform", "status", "last_seen_at", "created_at"]
    list_filter = ["status", "platform", "created_at", "last_seen_at"]
    search_fields = ["name", "owner__username", "owner__email", "platform"]
    readonly_fields = ["id", "token_hash", "last_seen_at", "created_at", "updated_at"]


@admin.register(PairingCode)
class PairingCodeAdmin(admin.ModelAdmin):
    list_display = ["code", "owner", "expires_at", "used_at", "created_at"]
    list_filter = ["expires_at", "used_at", "created_at"]
    search_fields = ["code", "owner__username", "owner__email"]
    readonly_fields = ["code", "created_at"]

