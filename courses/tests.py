from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from accounts.models import CustomUser
from .models import Course, Module
from .models import CourseProgress, ModuleProgress
from .serializers import ModuleSerializer


class ModuleSerializerQuizSupportTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(title={'en': 'Test Course'})

    def test_legacy_single_quiz_representation(self):
        module = Module.objects.create(
            course=self.course,
            title={'en': 'Module 1'},
            quiz={
                'question': {'en': 'Q1'},
                'options': {'en': ['A', 'B']},
                'correctIndex': 0,
            },
        )

        payload = ModuleSerializer(module).data

        self.assertEqual(payload['quiz']['question']['en'], 'Q1')
        self.assertEqual(len(payload['quizzes']), 1)
        self.assertEqual(payload['quizzes'][0]['question']['en'], 'Q1')

    def test_update_module_with_multiple_quizzes(self):
        module = Module.objects.create(
            course=self.course,
            title={'en': 'Module 2'},
            content={'en': 'Body'},
            quiz=[],
        )

        serializer = ModuleSerializer(module, data={
            'quizzes': [
                {
                    'question': {'en': 'Q1'},
                    'options': {'en': ['A', 'B']},
                    'correctIndex': 0,
                },
                {
                    'question': {'en': 'Q2'},
                    'options': {'en': ['C', 'D']},
                    'correctIndex': 1,
                },
            ],
        }, partial=True)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        module = serializer.save()

        self.assertEqual(len(module.quiz), 2)
        self.assertEqual(module.quiz[1]['question']['en'], 'Q2')

    def test_multi_answer_question_with_two_correct_indexes(self):
        module = Module.objects.create(
            course=self.course,
            title={'en': 'Module 3'},
            content={'en': 'Body'},
            quiz=[],
        )

        serializer = ModuleSerializer(module, data={
            'quizzes': [
                {
                    'question': {'en': 'Choose two'},
                    'options': {'en': ['A', 'B', 'C']},
                    'correctIndexes': [0, 2],
                }
            ],
        }, partial=True)

        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.quiz[0]['correctIndexes'], [0, 2])
        self.assertNotIn('correctIndex', updated.quiz[0])

    def test_multi_answer_question_rejects_more_than_three_answers(self):
        module = Module.objects.create(
            course=self.course,
            title={'en': 'Module 4'},
            content={'en': 'Body'},
            quiz=[],
        )

        serializer = ModuleSerializer(module, data={
            'quizzes': [
                {
                    'question': {'en': 'Choose too many'},
                    'options': {'en': ['A', 'B', 'C', 'D']},
                    'correctIndexes': [0, 1, 2, 3],
                }
            ],
        }, partial=True)

        self.assertFalse(serializer.is_valid())


class ProgressUpsertTests(APITestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email='tester@example.com',
            username='tester',
            password='password123',
        )
        self.client.force_authenticate(user=self.user)

        self.course = Course.objects.create(title={'en': 'Course'})
        self.module = Module.objects.create(course=self.course, title={'en': 'Module'})

    def test_module_progress_create_then_amend_keeps_same_id(self):
        url = reverse('progress-list')

        first = self.client.post(url, {'module': self.module.id, 'completed': False}, format='json')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        first_id = first.data['id']

        second = self.client.post(url, {'module': self.module.id, 'completed': True}, format='json')
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data['id'], first_id)

        progress = ModuleProgress.objects.get(user=self.user, module=self.module)
        self.assertTrue(progress.completed)

    def test_course_progress_create_then_amend_keeps_same_id(self):
        url = reverse('course-progress-list')

        first = self.client.post(
            url,
            {
                'course': self.course.id,
                'completed_modules': 1,
                'total_modules': 3,
                'progress': 0.33,
                'completed': False,
            },
            format='json',
        )
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        first_id = first.data['id']

        second = self.client.post(
            url,
            {
                'course': self.course.id,
                'completed_modules': 2,
                'total_modules': 3,
                'progress': 0.66,
                'completed': False,
            },
            format='json',
        )
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data['id'], first_id)

        progress = CourseProgress.objects.get(user=self.user, course=self.course)
        self.assertEqual(progress.completed_modules, 2)
        self.assertEqual(progress.total_modules, 3)
