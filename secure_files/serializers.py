from rest_framework import serializers
from .models import SecureFile


class SecureFileSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = SecureFile
        fields = ['id', 'owner', 'original_name', 'content_type', 'size', 'uploaded_at', 'download_url']
        read_only_fields = ['id', 'owner', 'original_name', 'content_type', 'size', 'uploaded_at', 'download_url']

    def get_download_url(self, obj):
        from .services.firebase_storage import generate_download_url
        try:
            return generate_download_url(obj.s3_key)
        except Exception:
            return None
