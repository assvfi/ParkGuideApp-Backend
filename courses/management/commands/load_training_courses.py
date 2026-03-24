import json
from django.core.management.base import BaseCommand
from courses.models import Course, Module


def normalize_quiz_payload(value):
    def normalize_quiz_item(item):
        if not isinstance(item, dict):
            return None

        if 'correctIndexes' in item and item.get('correctIndexes') is not None:
            correct_indexes = item.get('correctIndexes')
            if not isinstance(correct_indexes, list):
                return None
            valid_indexes = [index for index in correct_indexes if isinstance(index, int) and index >= 0]
        else:
            single_index = item.get('correctIndex')
            if not isinstance(single_index, int) or single_index < 0:
                return None
            valid_indexes = [single_index]

        unique_indexes = sorted(set(valid_indexes))[:3]
        if not unique_indexes:
            return None

        normalized_item = dict(item)
        normalized_item['correctIndexes'] = unique_indexes
        if len(unique_indexes) == 1:
            normalized_item['correctIndex'] = unique_indexes[0]
        else:
            normalized_item.pop('correctIndex', None)
        return normalized_item

    if value in (None, ''):
        return []
    if isinstance(value, dict):
        normalized = normalize_quiz_item(value)
        return [normalized] if normalized else []
    if isinstance(value, list):
        normalized_items = []
        for item in value:
            normalized_item = normalize_quiz_item(item)
            if normalized_item:
                normalized_items.append(normalized_item)
        return normalized_items
    return []

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
                raw_quizzes = module_data.get('quizzes', module_data.get('quiz', None))
                Module.objects.create(
                    course=course,
                    title=module_data.get('title'),
                    content=module_data.get('content'),
                    quiz=normalize_quiz_payload(raw_quizzes)
                )
        
        self.stdout.write(self.style.SUCCESS('Courses and modules loaded successfully'))