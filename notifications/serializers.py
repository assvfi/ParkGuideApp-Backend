from django.utils import timezone
from rest_framework import serializers
from .models import UserNotification


class UserNotificationSerializer(serializers.ModelSerializer):
    title = serializers.CharField(source='notification.title', read_only=True)
    description = serializers.CharField(source='notification.description', read_only=True)
    fullText = serializers.CharField(source='notification.full_text', read_only=True)
    time = serializers.SerializerMethodField()

    class Meta:
        model = UserNotification
        fields = ['id', 'title', 'description', 'fullText', 'time', 'is_read']

    def get_time(self, obj):
        now = timezone.now()
        delta = now - obj.notification.sent_at
        minutes = int(delta.total_seconds() // 60)

        if minutes < 1:
            return 'Just now'
        if minutes < 60:
            return f'{minutes} mins ago'
        if minutes < 1440:
            hours = minutes // 60
            return f'{hours} hours ago'
        return obj.notification.sent_at.strftime('%b %d, %Y')
