"""附件序列化器。"""
from rest_framework import serializers

from apps.attachments.models import Attachment


class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            "id", "object_type", "object_id", "filename", "mime_type", "size",
            "uploaded_by", "created_at",
        ]
        read_only_fields = fields

    def get_uploaded_by(self, obj) -> dict:
        return {"id": obj.uploaded_by_id, "username": obj.uploaded_by.username}


class AttachmentUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    object_type = serializers.ChoiceField(choices=[(t, t) for t in Attachment.OBJECT_TYPES])
    object_id = serializers.IntegerField(min_value=1)
    project_id = serializers.IntegerField(min_value=1)
