from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import CustomUser
from courses.models import Course, Module, ModuleProgress
from .models import Badge, UserBadge
from .services import (
    sync_pending_badges_for_eligible_users,
    auto_approve_pending_badges,
    auto_reject_pending_badges,
    revoke_badge_from_ineligible_users,
)


class BadgeServiceTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            email='admin@example.com',
            username='admin',
            password='password123',
            is_staff=True,
        )
        self.user1 = CustomUser.objects.create_user(
            email='user1@example.com',
            username='user1',
            password='password123',
        )
        self.user2 = CustomUser.objects.create_user(
            email='user2@example.com',
            username='user2',
            password='password123',
        )

        self.course = Course.objects.create(title={'en': 'Badge Course'})
        self.module1 = Module.objects.create(course=self.course, title={'en': 'M1'})
        self.module2 = Module.objects.create(course=self.course, title={'en': 'M2'})
        self.module3 = Module.objects.create(course=self.course, title={'en': 'M3'})

        ModuleProgress.objects.create(user=self.user1, module=self.module1, completed=True)
        ModuleProgress.objects.create(user=self.user1, module=self.module2, completed=True)
        ModuleProgress.objects.create(user=self.user2, module=self.module1, completed=True)

        self.badge = Badge.objects.create(
            name='Explorer',
            required_completed_modules=2,
            is_active=True,
        )

    def test_sync_pending_badges_for_eligible_users(self):
        created_pending, moved_to_pending, auto_granted = sync_pending_badges_for_eligible_users(
            self.badge,
            admin_user=self.admin,
        )

        self.assertEqual(created_pending, 1)
        self.assertEqual(moved_to_pending, 0)
        self.assertEqual(auto_granted, 0)

        user_badge = UserBadge.objects.get(user=self.user1, badge=self.badge)
        self.assertEqual(user_badge.status, UserBadge.STATUS_PENDING)
        self.assertFalse(user_badge.is_awarded)

    def test_revoke_badge_when_user_becomes_ineligible(self):
        sync_pending_badges_for_eligible_users(self.badge, admin_user=self.admin)
        auto_approve_pending_badges(self.badge, admin_user=self.admin)
        user_badge = UserBadge.objects.get(user=self.user1, badge=self.badge)

        progress_row = ModuleProgress.objects.get(user=self.user1, module=self.module2)
        progress_row.completed = False
        progress_row.save(update_fields=['completed'])

        revoked = revoke_badge_from_ineligible_users(self.badge, admin_user=self.admin)

        self.assertEqual(revoked, 1)

        user_badge.refresh_from_db()
        self.assertEqual(user_badge.status, UserBadge.STATUS_REJECTED)
        self.assertFalse(user_badge.is_awarded)
        self.assertEqual(user_badge.revoked_by, self.admin)

    def test_auto_approve_pending_keeps_same_row(self):
        sync_pending_badges_for_eligible_users(self.badge, admin_user=self.admin)
        user_badge = UserBadge.objects.get(user=self.user1, badge=self.badge)
        existing_id = user_badge.id

        approved = auto_approve_pending_badges(self.badge, admin_user=self.admin)
        self.assertEqual(approved, 1)

        same_row = UserBadge.objects.get(user=self.user1, badge=self.badge)
        self.assertEqual(same_row.id, existing_id)
        self.assertEqual(same_row.status, UserBadge.STATUS_GRANTED)
        self.assertTrue(same_row.is_awarded)

    def test_auto_reject_pending_badges(self):
        sync_pending_badges_for_eligible_users(self.badge, admin_user=self.admin)
        rejected = auto_reject_pending_badges(self.badge, admin_user=self.admin)

        self.assertEqual(rejected, 1)
        user_badge = UserBadge.objects.get(user=self.user1, badge=self.badge)
        self.assertEqual(user_badge.status, UserBadge.STATUS_REJECTED)
        self.assertFalse(user_badge.is_awarded)

    def test_course_specific_badge_awards_based_on_selected_course_only(self):
        other_course = Course.objects.create(title={'en': 'Other Course'})
        other_module1 = Module.objects.create(course=other_course, title={'en': 'O1'})
        other_module2 = Module.objects.create(course=other_course, title={'en': 'O2'})

        ModuleProgress.objects.create(user=self.user2, module=other_module1, completed=True)
        ModuleProgress.objects.create(user=self.user2, module=other_module2, completed=True)

        course_badge = Badge.objects.create(
            name='Badge Course Completion',
            course=self.course,
            required_completed_modules=2,
            is_active=True,
        )

        created_pending, moved_to_pending, auto_granted = sync_pending_badges_for_eligible_users(
            course_badge,
            admin_user=self.admin,
        )

        self.assertEqual(created_pending, 1)
        self.assertEqual(moved_to_pending, 0)
        self.assertEqual(auto_granted, 0)
        self.assertTrue(UserBadge.objects.filter(user=self.user1, badge=course_badge, status=UserBadge.STATUS_PENDING).exists())
        self.assertFalse(UserBadge.objects.filter(user=self.user2, badge=course_badge).exists())


class BadgeApiTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='apiuser@example.com',
            username='apiuser',
            password='password123',
        )
        self.client.force_authenticate(user=self.user)

        self.course = Course.objects.create(title={'en': 'API Course'})
        self.module = Module.objects.create(course=self.course, title={'en': 'Module A'})
        ModuleProgress.objects.create(user=self.user, module=self.module, completed=True)

        self.badge = Badge.objects.create(
            name='API Badge',
            course=self.course,
            required_completed_modules=1,
            is_active=True,
        )

    def test_badges_endpoint_returns_eligibility(self):
        url = reverse('badge-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'API Badge')
        self.assertTrue(response.data[0]['eligible'])
        self.assertFalse(response.data[0]['pending'])
        self.assertFalse(response.data[0]['earned'])

    def test_my_badges_endpoint_returns_awarded_badges(self):
        UserBadge.objects.create(
            user=self.user,
            badge=self.badge,
            status=UserBadge.STATUS_GRANTED,
            is_awarded=True,
        )

        url = reverse('my-badge-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['badge_name'], 'API Badge')
