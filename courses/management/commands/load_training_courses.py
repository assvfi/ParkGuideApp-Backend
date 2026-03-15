import json
from django.core.management.base import BaseCommand
from courses.models import Course, Module

class Command(BaseCommand):
    help = "Load courses and modules from JSON"

    def handle(self, *args, **kwargs):
        # Clear old data
        Course.objects.all().delete()
        Module.objects.all().delete()

        # Load JSON
        with open('courses/data/training_courses.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Create courses & modules
        for course_data in data:
            course = Course.objects.create(title=course_data['title'])
            for module_data in course_data.get('modules', []):
                Module.objects.create(
                    course=course,
                    title=module_data.get('title'),
                    content=module_data.get('content'),
                    quiz=module_data.get('quiz', None)
                )
        
        self.stdout.write(self.style.SUCCESS('Courses and modules loaded successfully'))