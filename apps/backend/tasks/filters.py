import django_filters

from .models import Task


class TaskFilter(django_filters.FilterSet):
    created_after = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    created_before = django_filters.IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")

    class Meta:
        model = Task
        fields = ["status", "agent_type", "device", "project", "session", "created_after", "created_before"]
