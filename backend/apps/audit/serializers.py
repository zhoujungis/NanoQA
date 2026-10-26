from rest_framework import serializers

from apps.audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True, default=None)
    display_name = serializers.CharField(source="user.display_name", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id", "action", "object_type", "object_id", "object_ref",
            "old_data", "new_data", "username", "display_name",
            "ip_address", "request_id", "created_at",
        ]
