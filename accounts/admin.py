from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count, Q
from django.utils.html import format_html

from courses.models import CourseProgress
from park_guide.admin_mixins import DashboardStatsChangeListMixin
from user_progress.models import UserBadge

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(DashboardStatsChangeListMixin, UserAdmin):
    model = CustomUser
    list_display = (
        'email',
        'username',
        'user_type',
        'role_badge',
        'learner_activity',
        'course_completion_summary',
        'badge_summary',
        'is_active',
        'last_login',
    )
    list_filter = ('user_type', 'is_staff', 'is_active', 'is_superuser', 'date_joined', 'last_login')
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Permissions', {'fields': ('user_type', 'is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'user_type', 'password1', 'password2', 'is_staff', 'is_active', 'is_superuser')}
        ),
    )
    search_fields = ('email', 'username')
    ordering = ('email',)
    dashboard_title = 'User Operations'
    dashboard_description = 'Monitor staff access, learner activity, completions, and badge readiness from one screen.'

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.annotate(
            completed_modules_count=Count('moduleprogress', filter=Q(moduleprogress__completed=True), distinct=True),
            user_courses_total=Count('courseprogress', distinct=True),
            user_courses_completed=Count('courseprogress', filter=Q(courseprogress__completed=True), distinct=True),
            badge_pending_count=Count('badge_progress', filter=Q(badge_progress__status=UserBadge.STATUS_PENDING), distinct=True),
            badge_granted_count=Count('badge_progress', filter=Q(badge_progress__status=UserBadge.STATUS_GRANTED), distinct=True),
        )

    def role_badge(self, obj):
        if obj.user_type == CustomUser.USER_TYPE_ADMIN or obj.is_superuser:
            return self.render_status_pill('Superuser', 'gold')
        if obj.is_staff:
            return self.render_status_pill('Staff', 'blue')
        return self.render_status_pill('Learner', 'green')
    role_badge.short_description = 'Role'

    def learner_activity(self, obj):
        if obj.user_type == CustomUser.USER_TYPE_ADMIN or obj.is_staff or obj.is_superuser:
            return self.render_status_pill('Internal account', 'neutral')
        completed_modules = getattr(obj, 'completed_modules_count', 0)
        if completed_modules >= 8:
            return self.render_status_pill(f'{completed_modules} modules done', 'green')
        if completed_modules >= 1:
            return self.render_status_pill(f'{completed_modules} modules active', 'blue')
        return self.render_status_pill('No module activity', 'neutral')
    learner_activity.short_description = 'Activity'

    def course_completion_summary(self, obj):
        if obj.user_type == CustomUser.USER_TYPE_ADMIN or obj.is_staff or obj.is_superuser:
            return format_html('<span class="admin-subtle">{}</span>', 'Not a learner account')

        total = getattr(obj, 'user_courses_total', None)
        completed = getattr(obj, 'user_courses_completed', None)
        if total is None or completed is None:
            records = CourseProgress.objects.filter(user=obj)
            total = records.count()
            completed = records.filter(completed=True).count()
        percent = 0 if total == 0 else (completed / total) * 100
        return self.render_progress_bar(percent, f'{completed}/{total} courses', tone='green')
    course_completion_summary.short_description = 'Course completion'

    def badge_summary(self, obj):
        pending = getattr(obj, 'badge_pending_count', 0)
        granted = getattr(obj, 'badge_granted_count', 0)
        if pending or granted:
            return format_html(
                '<div><strong>{}</strong> granted<br><span class="admin-subtle">{} pending</span></div>',
                granted,
                pending,
            )
        return format_html('<span class="admin-subtle">{}</span>', 'No badge records')
    badge_summary.short_description = 'Badges'

    def get_dashboard_stats(self, request, queryset):
        learners = queryset.filter(user_type=CustomUser.USER_TYPE_LEARNER, is_staff=False, is_superuser=False)
        active = queryset.filter(is_active=True).count()
        completed_courses = CourseProgress.objects.filter(user__in=queryset, completed=True).count()
        granted_badges = UserBadge.objects.filter(user__in=queryset, status=UserBadge.STATUS_GRANTED).count()
        return [
            {'label': 'Visible users', 'value': queryset.count()},
            {'label': 'Active accounts', 'value': active},
            {'label': 'Course completions', 'value': completed_courses},
            {'label': 'Granted badges', 'value': granted_badges},
            {'label': 'Learners', 'value': learners.count()},
        ]
