from __future__ import annotations

from rest_framework import serializers

from .models import Device, PairingCode
from .services import create_pairing_code, pair_device


class DeviceProjectSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    local_path = serializers.CharField(read_only=True)
    repository_url = serializers.CharField(read_only=True)
    default_model = serializers.CharField(read_only=True)
    default_profile = serializers.CharField(read_only=True)
    default_sandbox = serializers.CharField(read_only=True)
    default_approval_policy = serializers.CharField(read_only=True)
    is_active = serializers.BooleanField(read_only=True)


class DeviceSerializer(serializers.ModelSerializer):
    project_count = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source="owner.username", read_only=True)

    class Meta:
        model = Device
        fields = [
            "id",
            "owner_username",
            "name",
            "platform",
            "status",
            "capabilities_updated_at",
            "last_seen_at",
            "project_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner_username",
            "platform",
            "status",
            "capabilities_updated_at",
            "last_seen_at",
            "project_count",
            "created_at",
            "updated_at",
        ]

    def get_project_count(self, obj: Device) -> int:
        annotated_count = getattr(obj, "project_count", None)
        if annotated_count is not None:
            return annotated_count
        return obj.projects.filter(is_active=True).count()


class DeviceDetailSerializer(DeviceSerializer):
    projects = DeviceProjectSerializer(many=True, read_only=True)

    class Meta(DeviceSerializer.Meta):
        fields = DeviceSerializer.Meta.fields + ["projects"]


class PairingCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = PairingCode
        fields = ["code", "expires_at", "created_at"]
        read_only_fields = ["code", "expires_at", "created_at"]

    def create(self, validated_data):
        return create_pairing_code(self.context["request"].user)


class PairDeviceSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=12)
    name = serializers.CharField(max_length=120)
    platform = serializers.CharField(max_length=80, allow_blank=True, required=False)
    project_path = serializers.CharField(max_length=500, required=False, allow_blank=True)
    project_name = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def create(self, validated_data):
        return pair_device(
            code=validated_data["code"],
            name=validated_data["name"],
            platform=validated_data.get("platform", ""),
            project_path=validated_data.get("project_path", ""),
            project_name=validated_data.get("project_name", ""),
        )


class DeviceCapabilitiesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ["id", "capabilities", "capabilities_updated_at"]
        read_only_fields = fields
