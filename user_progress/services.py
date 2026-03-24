from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from courses.models import ModuleProgress
from .models import UserBadge


def get_user_completed_module_counts(user_ids=None):
    queryset = ModuleProgress.objects.filter(completed=True)
    if user_ids is not None:
        queryset = queryset.filter(user_id__in=user_ids)

    rows = queryset.values('user_id').annotate(completed_modules=Count('id'))
    return {row['user_id']: row['completed_modules'] for row in rows}


def get_user_completed_module_counts_for_badge(badge, user_ids=None):
    queryset = ModuleProgress.objects.filter(completed=True)
    if badge.course_id:
        queryset = queryset.filter(module__course=badge.course)
    if user_ids is not None:
        queryset = queryset.filter(user_id__in=user_ids)

    rows = queryset.values('user_id').annotate(completed_modules=Count('id'))
    return {row['user_id']: row['completed_modules'] for row in rows}


def sync_pending_badges_for_eligible_users(badge, admin_user=None):
    if not badge.is_active:
        return 0, 0, 0

    completed_counts = get_user_completed_module_counts_for_badge(badge)
    eligible_user_ids = [
        user_id
        for user_id, completed in completed_counts.items()
        if completed >= badge.required_completed_modules
    ]

    if not eligible_user_ids:
        return 0, 0, 0

    User = get_user_model()
    users = User.objects.filter(id__in=eligible_user_ids)

    created_pending_count = 0
    moved_to_pending_count = 0
    auto_granted_count = 0

    for user in users:
        user_badge, created = UserBadge.objects.get_or_create(
            user=user,
            badge=badge,
            defaults={
                'status': UserBadge.STATUS_GRANTED if badge.auto_approve_when_eligible else UserBadge.STATUS_PENDING,
                'is_awarded': bool(badge.auto_approve_when_eligible),
                'awarded_by': admin_user if badge.auto_approve_when_eligible else None,
                'revoked_at': None,
                'revoked_by': None,
            },
        )

        if created:
            if badge.auto_approve_when_eligible:
                auto_granted_count += 1
            else:
                created_pending_count += 1
            continue

        if user_badge.status == UserBadge.STATUS_GRANTED:
            continue

        if badge.auto_approve_when_eligible:
            user_badge.status = UserBadge.STATUS_GRANTED
            user_badge.is_awarded = True
            user_badge.awarded_by = admin_user
            user_badge.revoked_at = None
            user_badge.revoked_by = None
            user_badge.save(update_fields=['status', 'is_awarded', 'awarded_by', 'revoked_at', 'revoked_by'])
            auto_granted_count += 1
            continue

        user_badge.status = UserBadge.STATUS_PENDING
        user_badge.is_awarded = False
        user_badge.awarded_by = None
        user_badge.revoked_at = None
        user_badge.revoked_by = None
        user_badge.save(update_fields=['status', 'is_awarded', 'awarded_by', 'revoked_at', 'revoked_by'])
        moved_to_pending_count += 1

    return created_pending_count, moved_to_pending_count, auto_granted_count


def auto_approve_pending_badges(badge, admin_user=None):
    pending_badges = UserBadge.objects.filter(badge=badge, status=UserBadge.STATUS_PENDING).select_related('user')
    if not pending_badges.exists():
        return 0

    user_ids = [row.user_id for row in pending_badges]
    completed_counts = get_user_completed_module_counts_for_badge(badge, user_ids=user_ids)

    approved_count = 0
    for user_badge in pending_badges:
        completed_modules = completed_counts.get(user_badge.user_id, 0)
        if completed_modules < badge.required_completed_modules:
            continue

        user_badge.status = UserBadge.STATUS_GRANTED
        user_badge.is_awarded = True
        user_badge.awarded_by = admin_user
        user_badge.revoked_at = None
        user_badge.revoked_by = None
        user_badge.save(update_fields=['status', 'is_awarded', 'awarded_by', 'revoked_at', 'revoked_by'])
        approved_count += 1

    return approved_count


def auto_reject_pending_badges(badge, admin_user=None):
    pending_badges = UserBadge.objects.filter(badge=badge, status=UserBadge.STATUS_PENDING)
    if not pending_badges.exists():
        return 0

    now = timezone.now()
    rejected_count = 0

    for user_badge in pending_badges:
        user_badge.status = UserBadge.STATUS_REJECTED
        user_badge.is_awarded = False
        user_badge.revoked_at = now
        user_badge.revoked_by = admin_user
        user_badge.save(update_fields=['status', 'is_awarded', 'revoked_at', 'revoked_by'])
        rejected_count += 1

    return rejected_count

def revoke_badge_from_ineligible_users(badge, admin_user=None):
    active_badges = UserBadge.objects.filter(badge=badge, status=UserBadge.STATUS_GRANTED).select_related('user')
    if not active_badges.exists():
        return 0

    user_ids = [item.user_id for item in active_badges]
    completed_counts = get_user_completed_module_counts_for_badge(badge, user_ids=user_ids)

    revoked_count = 0
    now = timezone.now()

    for user_badge in active_badges:
        completed_modules = completed_counts.get(user_badge.user_id, 0)
        if completed_modules >= badge.required_completed_modules:
            continue

        user_badge.status = UserBadge.STATUS_REJECTED
        user_badge.is_awarded = False
        user_badge.revoked_at = now
        user_badge.revoked_by = admin_user
        user_badge.save(update_fields=['status', 'is_awarded', 'revoked_at', 'revoked_by'])
        revoked_count += 1

    return revoked_count
