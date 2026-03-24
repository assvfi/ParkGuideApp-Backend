from django.core.management.base import BaseCommand
from django.db import transaction
from courses.models import Course
from user_progress.models import Badge


class Command(BaseCommand):
    help = 'Create selectable demo badges based on available training course/module data.'

    @transaction.atomic
    def handle(self, *args, **options):
        courses = Course.objects.prefetch_related('modules').all()
        if not courses.exists():
            self.stdout.write(self.style.WARNING('No courses found. Load training courses first.'))
            return

        total_modules = sum(course.modules.count() for course in courses)
        half_modules = max(1, total_modules // 2)

        global_badges = [
            {
                'name': 'Training Starter',
                'description': 'Complete at least 1 module across all courses.',
                'required_completed_modules': 1,
                'course': None,
                'is_active': True,
            },
            {
                'name': 'Training Explorer',
                'description': 'Complete at least half of all available training modules.',
                'required_completed_modules': half_modules,
                'course': None,
                'is_active': True,
            },
            {
                'name': 'Training Master',
                'description': 'Complete all available training modules.',
                'required_completed_modules': max(1, total_modules),
                'course': None,
                'is_active': True,
            },
        ]

        created_count = 0
        updated_count = 0

        for payload in global_badges:
            _, created = Badge.objects.update_or_create(
                name=payload['name'],
                defaults=payload,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        for course in courses:
            module_count = max(1, course.modules.count())
            course_title = course.title.get('en', f'Course {course.id}')
            badge_name = f'{course_title} Completion'
            payload = {
                'description': f'Complete all modules in {course_title}.',
                'required_completed_modules': module_count,
                'course': course,
                'is_active': True,
            }
            _, created = Badge.objects.update_or_create(
                name=badge_name,
                defaults=payload,
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Demo badges ready. Created: {created_count}, Updated: {updated_count}'
            )
        )
