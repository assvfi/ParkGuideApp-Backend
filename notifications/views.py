from django.utils import timezone
from rest_framework import permissions, status, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Notification, UserNotification, PushToken
from .serializers import UserNotificationSerializer, PushTokenSerializer

class UserNotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserNotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserNotification.objects.filter(user=self.request.user).select_related('notification')

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        user_notification = self.get_object()
        now = timezone.now()
        if not user_notification.is_read:
            user_notification.is_read = True
            user_notification.read_at = now
            user_notification.save(update_fields=['is_read', 'read_at'])
        # if any admin reads it, it counts as read for all admins
        if request.user.is_staff:
            Notification.objects.filter(id=user_notification.notification_id).update(admin_seen_at=now, admin_seen_by=request.user)
        return Response(self.get_serializer(user_notification).data)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        now = timezone.now()
        unread_qs = self.get_queryset().filter(is_read=False)
        notification_ids = list(unread_qs.values_list('notification_id', flat=True).distinct())
        updated = unread_qs.update(is_read=True, read_at=now)
        if request.user.is_staff and notification_ids:
            Notification.objects.filter(id__in=notification_ids).update(admin_seen_at=now, admin_seen_by=request.user)
        return Response({'updated': updated}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='clear-read')
    def clear_read(self, request):
        deleted, _ = self.get_queryset().filter(is_read=True).delete()
        return Response({'deleted': deleted}, status=status.HTTP_200_OK)


class PushTokenViewSet(viewsets.ModelViewSet):
    serializer_class = PushTokenSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ['get', 'post', 'delete']

    def get_queryset(self):
        return PushToken.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        """Override create to handle duplicate tokens gracefully"""
        token = request.data.get('token')
        device_type = request.data.get('device_type', 'ios')
        
        # Try to update existing token for this user, or create new one
        push_token, created = PushToken.objects.update_or_create(
            user=request.user,
            token=token,
            defaults={
                'device_type': device_type,
                'is_active': True,
            }
        )
        
        serializer = self.get_serializer(push_token)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(serializer.data, status=status_code)

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        push_token = self.get_object()
        push_token.is_active = False
        push_token.save()
        return Response({'status': 'token deactivated'}, status=status.HTTP_200_OK)