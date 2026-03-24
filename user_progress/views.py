from rest_framework import permissions, viewsets
from .models import Badge, UserBadge
from .serializers import BadgeStatusSerializer, UserBadgeSerializer


class BadgeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BadgeStatusSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Badge.objects.filter(is_active=True).select_related('course')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        badges = list(self.get_queryset())

        status_rows = UserBadge.objects.filter(
            user=user,
            badge_id__in=[badge.id for badge in badges],
        ).values_list('badge_id', 'status')
        status_map = {badge_id: status for badge_id, status in status_rows}

        global_completed = (
            user.moduleprogress_set.filter(completed=True).count()
            if hasattr(user, 'moduleprogress_set')
            else 0
        )

        completed_count_map = {}
        for badge in badges:
            if badge.course_id:
                completed_count = user.moduleprogress_set.filter(
                    completed=True,
                    module__course=badge.course,
                ).count()
            else:
                completed_count = global_completed
            completed_count_map[badge.id] = completed_count

        context['status_map'] = status_map
        context['completed_count_map'] = completed_count_map
        return context


class MyBadgeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserBadgeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserBadge.objects.filter(
            user=self.request.user,
            status=UserBadge.STATUS_GRANTED,
        ).select_related('badge', 'badge__course')
