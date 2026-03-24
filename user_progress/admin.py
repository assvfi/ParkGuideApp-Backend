from django.contrib import admin
from .models import ModuleProgressRecord, CourseProgressRecord, Badge, UserBadge
from .services import (
    sync_pending_badges_for_eligible_users,
    auto_approve_pending_badges,
    auto_reject_pending_badges,
    revoke_badge_from_ineligible_users,
)


@admin.register(ModuleProgressRecord)
class ModuleProgressRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'module', 'completed', 'completed_at')
    list_filter = ('completed', 'completed_at', 'module__course')
    search_fields = ('user__email', 'user__username', 'module__title')
    autocomplete_fields = ('user', 'module')
    ordering = ('-completed_at',)


@admin.register(CourseProgressRecord)
class CourseProgressRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'course', 'completed_modules', 'total_modules', 'progress', 'completed', 'updated_at')
    list_filter = ('completed', 'updated_at', 'course')
    search_fields = ('user__email', 'user__username', 'course__title')
    autocomplete_fields = ('user', 'course')
    ordering = ('-updated_at',)


@admin.register(Badge)
class BadgeAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name',
        'course',
        'required_completed_modules',
        'auto_approve_when_eligible',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'course')
    search_fields = ('name', 'description', 'course__title')
    ordering = ('course', 'required_completed_modules', 'name')
    autocomplete_fields = ('course',)
    actions = (
        'sync_then_auto_approve_for_selected_badges',
        'sync_pending_for_eligible_users',
        'auto_approve_pending_for_selected_badges',
        'auto_reject_pending_for_selected_badges',
        'revoke_from_ineligible_users',
    )

    @admin.action(description='Sync pending then auto approve eligible users')
    def sync_then_auto_approve_for_selected_badges(self, request, queryset):
        created_pending_total = 0
        moved_to_pending_total = 0
        auto_granted_during_sync_total = 0
        approved_after_sync_total = 0

        for badge in queryset:
            created_pending, moved_to_pending, auto_granted_during_sync = sync_pending_badges_for_eligible_users(
                badge,
                admin_user=request.user,
            )
            approved_after_sync = auto_approve_pending_badges(badge, admin_user=request.user)

            created_pending_total += created_pending
            moved_to_pending_total += moved_to_pending
            auto_granted_during_sync_total += auto_granted_during_sync
            approved_after_sync_total += approved_after_sync

        self.message_user(
            request,
            (
                f'Sync+approve complete. Pending created: {created_pending_total}, '
                f'moved to pending: {moved_to_pending_total}, '
                f'auto-granted during sync: {auto_granted_during_sync_total}, '
                f'approved after sync: {approved_after_sync_total}.'
            ),
        )

    @admin.action(description='Sync pending badges for eligible users')
    def sync_pending_for_eligible_users(self, request, queryset):
        created_pending_total = 0
        moved_to_pending_total = 0
        auto_granted_total = 0

        for badge in queryset:
            created_pending, moved_to_pending, auto_granted = sync_pending_badges_for_eligible_users(
                badge,
                admin_user=request.user,
            )
            created_pending_total += created_pending
            moved_to_pending_total += moved_to_pending
            auto_granted_total += auto_granted

        self.message_user(
            request,
            (
                f'Pending created: {created_pending_total}, '
                f'moved to pending: {moved_to_pending_total}, '
                f'auto-granted: {auto_granted_total}.'
            ),
        )

    @admin.action(description='Auto approve pending users for selected badges')
    def auto_approve_pending_for_selected_badges(self, request, queryset):
        approved_total = 0
        for badge in queryset:
            approved_total += auto_approve_pending_badges(badge, admin_user=request.user)

        self.message_user(request, f'Approved {approved_total} pending badge records.')

    @admin.action(description='Auto reject pending users for selected badges')
    def auto_reject_pending_for_selected_badges(self, request, queryset):
        rejected_total = 0
        for badge in queryset:
            rejected_total += auto_reject_pending_badges(badge, admin_user=request.user)

        self.message_user(request, f'Rejected {rejected_total} pending badge records.')

    @admin.action(description='Revoke selected badges from ineligible users')
    def revoke_from_ineligible_users(self, request, queryset):
        revoked_total = 0

        for badge in queryset:
            revoked_total += revoke_badge_from_ineligible_users(badge, admin_user=request.user)

        self.message_user(request, f'Revoked {revoked_total} badge records from ineligible users.')


@admin.register(UserBadge)
class UserBadgeAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'badge', 'status', 'is_awarded', 'awarded_at', 'revoked_at')
    list_filter = ('status', 'is_awarded', 'badge', 'awarded_at', 'revoked_at')
    search_fields = ('user__email', 'user__username', 'badge__name')
    autocomplete_fields = ('user', 'badge', 'awarded_by', 'revoked_by')
    ordering = ('-awarded_at',)
