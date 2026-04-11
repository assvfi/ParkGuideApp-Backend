from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.utils import timezone
import logging

from park_guide.admin_mixins import DashboardStatsChangeListMixin

from .models import Notification, UserNotification
from .services import send_push_to_users

logger = logging.getLogger(__name__)


@admin.register(Notification)
class NotificationAdmin(DashboardStatsChangeListMixin, admin.ModelAdmin):
    list_display = ('id', 'title', 'sent_at', 'created_by')
    search_fields = ('title', 'description', 'full_text')
    readonly_fields = ('sent_at',)
    actions = ('send_to_all_users',)
    dashboard_title = 'Communications'
    dashboard_description = 'Create announcements and keep outreach to park guide users organized.'

    def _deliver_to_app_users(self, notifications_queryset):
        print(f"\n=== _DELIVER_TO_APP_USERS CALLED ===")
        User = get_user_model()
        users = User.objects.filter(is_active=True, is_staff=False, is_superuser=False)
        
        print(f"Found {users.count()} app users to deliver to")
        logger.info(f"Found {users.count()} app users to deliver to")

        user_ids = list(users.values_list('id', flat=True))
        notification_ids = list(notifications_queryset.values_list('id', flat=True))

        print(f"User IDs: {user_ids}, Notification IDs: {notification_ids}")
        
        if not user_ids or not notification_ids:
            print(f"Delivery aborted: user_ids={len(user_ids)}, notification_ids={len(notification_ids)}")
            logger.warning(f"Delivery aborted: user_ids={len(user_ids)}, notification_ids={len(notification_ids)}")
            return 0, len(user_ids), []

        existing_pairs = set(
            UserNotification.objects.filter(
                user_id__in=user_ids,
                notification_id__in=notification_ids,
            ).values_list('user_id', 'notification_id')
        )

        to_create = []
        for notification_id in notification_ids:
            for user_id in user_ids:
                pair = (user_id, notification_id)
                if pair in existing_pairs:
                    continue
                to_create.append(UserNotification(user_id=user_id, notification_id=notification_id))

        UserNotification.objects.bulk_create(to_create, ignore_conflicts=True)
        print(f"Created {len(to_create)} UserNotification entries")
        
        # Get the actual notification objects to send push with their details
        notifications = notifications_queryset.values_list('title', 'description', flat=False)
        print(f"About to return {len(list(users))} users for push notification")
        logger.info(f"About to return {len(list(users))} users for push notification")
        
        return len(to_create), len(user_ids), list(users)

    def save_model(self, request, obj, form, change):
        print(f"\n=== NOTIFICATION SAVE_MODEL CALLED ===")
        print(f"Change: {change}, Title: {obj.title}")
        
        if not change and not obj.created_by_id:
            obj.created_by = request.user

        super().save_model(request, obj, form, change)

        if not change:
            print(f"New notification created, attempting to deliver...")
            logger.info(f"Creating notification: {obj.title}")
            created_count, user_count, users = self._deliver_to_app_users(Notification.objects.filter(id=obj.id))
            print(f"Delivered to {user_count} users, found {len(users)} users with tokens")
            logger.info(f"Delivered to {user_count} users, found {len(users)} users with tokens")
            
            # Send push notifications to all users
            if users:
                try:
                    print(f"Sending push notification to {len(users)} users")
                    logger.info(f"Sending push notification to {len(users)} users")
                    send_push_to_users(users, obj.title, obj.description)
                    print("Push notifications sent successfully")
                    logger.info("Push notifications sent successfully")
                    self.message_user(
                        request,
                        f'Notification sent immediately to {user_count} app users. Created {created_count} delivery entries. Push notifications sent.',
                        level=messages.SUCCESS,
                    )
                except Exception as e:
                    print(f"Push notification failed: {str(e)}")
                    logger.error(f"Push notification failed: {str(e)}", exc_info=True)
                    self.message_user(request, f'Notification created but push sending failed: {str(e)}', level=messages.WARNING)
            else:
                print("No active users found to send push notifications to")
                logger.warning("No active users found to send push notifications to")
                self.message_user(
                    request,
                    f'Notification created but no active users to send to.',
                    level=messages.WARNING,
                )

    @admin.action(description='Send selected notifications to all app users')
    def send_to_all_users(self, request, queryset):
        created_count, user_count, users = self._deliver_to_app_users(queryset)
        
        # Send push notifications for each notification being sent
        success_count = 0
        for notification in queryset:
            if users:
                try:
                    send_push_to_users(users, notification.title, notification.description)
                    success_count += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f'Failed to send push for "{notification.title}": {str(e)}',
                        level=messages.WARNING
                    )

        self.message_user(
            request,
            f'Sent {queryset.count()} notifications to {user_count} app users. Created {created_count} new user notification entries. Push sent for {success_count}/{queryset.count()} notifications.',
            level=messages.SUCCESS,
        )

    def get_dashboard_stats(self, request, queryset):
        today = timezone.localdate()
        return [
            {'label': 'Messages', 'value': queryset.count()},
            {'label': 'Created today', 'value': queryset.filter(sent_at__date=today).count()},
            {'label': 'Delivery rows', 'value': UserNotification.objects.count()},
        ]


@admin.register(UserNotification)
class UserNotificationAdmin(DashboardStatsChangeListMixin, admin.ModelAdmin):
    list_display = ('id', 'user', 'notification', 'is_read', 'read_at')
    list_filter = ('is_read', 'read_at')
    search_fields = ('user__email', 'user__username', 'notification__title')
    autocomplete_fields = ('user', 'notification')
    ordering = ('-notification__sent_at',)
    dashboard_title = 'Notification Delivery'
    dashboard_description = 'Follow read status and see which alerts still have not been opened.'

    def get_dashboard_stats(self, request, queryset):
        total = queryset.count()
        unread = queryset.filter(is_read=False).count()
        return [
            {'label': 'Visible deliveries', 'value': total},
            {'label': 'Unread', 'value': unread},
            {'label': 'Read', 'value': total - unread},
        ]
