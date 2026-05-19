"""
Fresh, clean API views for courses
Simple CRUD operations with proper HTTP method handling
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db import IntegrityError
from django.db.models import Q
from django.db.models import Max

from courses.models import (
    Course, Chapter, Lesson, PracticeExercise, Quiz,
    LessonProgress, QuizAttempt, PracticeAttempt, CourseEnrollment,
    ChapterProgress,
)
from courses.serializers_fresh import (
    CourseListSerializer, CourseDetailSerializer, CourseCreateUpdateSerializer,
    CourseEnrollmentSerializer,
    ChapterListSerializer, ChapterDetailSerializer, ChapterCreateUpdateSerializer,
    LessonSerializer, LessonCreateUpdateSerializer,
    PracticeExerciseSerializer, PracticeExerciseCreateUpdateSerializer,
    QuizSerializer, QuizCreateUpdateSerializer,
)
from courses.prerequisite_utils import get_effective_prerequisite_codes

import logging
logger = logging.getLogger(__name__)


def update_chapter_progress_for_user(user, chapter):
    """Recalculate chapter progress using the same rules as the legacy API."""
    lessons = chapter.lessons.all()
    completed_lessons = LessonProgress.objects.filter(
        user=user,
        lesson__in=lessons,
        completed=True,
    ).count()
    total_lessons = lessons.count()

    has_practice = chapter.practice_exercises.exists()
    has_quiz = chapter.quizzes.exists()

    component_count = 1
    if has_practice:
        component_count += 1
    if has_quiz:
        component_count += 1

    pct_per_component = 100 / component_count
    lessons_progress = (completed_lessons / total_lessons * pct_per_component) if total_lessons > 0 else 0

    practice_score = None
    practice_passed = False
    practice_progress = 0
    if has_practice:
        practice = chapter.practice_exercises.first()
        best_practice = PracticeAttempt.objects.filter(
            user=user,
            exercise=practice,
        ).order_by('-score').first()
        if best_practice:
            practice_score = best_practice.score
            practice_passed = best_practice.passed
            if practice_passed:
                practice_progress = pct_per_component
    else:
        practice_passed = True
        practice_progress = pct_per_component

    quiz_score = None
    quiz_passed = False
    quiz_progress = 0
    if has_quiz:
        quiz = chapter.quizzes.first()
        best_quiz = QuizAttempt.objects.filter(
            user=user,
            quiz=quiz,
        ).order_by('-score').first()
        if best_quiz:
            quiz_score = best_quiz.score
            quiz_passed = best_quiz.passed
            if quiz_passed:
                quiz_progress = pct_per_component
    else:
        quiz_passed = True
        quiz_progress = pct_per_component

    progress_percentage = min(100, lessons_progress + practice_progress + quiz_progress)
    is_complete = completed_lessons == total_lessons and practice_passed and quiz_passed

    ChapterProgress.objects.update_or_create(
        user=user,
        chapter=chapter,
        defaults={
            'completed_lessons': completed_lessons,
            'total_lessons': total_lessons,
            'practice_completed': practice_passed,
            'practice_score': practice_score,
            'practice_passed': practice_passed,
            'quiz_completed': quiz_passed,
            'quiz_score': quiz_score,
            'quiz_passed': quiz_passed,
            'progress_percentage': progress_percentage,
            'is_complete': is_complete,
            'started_at': timezone.now(),
            'completed_at': timezone.now() if is_complete else None,
        },
    )


def update_course_enrollment_progress(user, course):
    """Recalculate course enrollment progress from chapter progress."""
    from user_progress.services import grant_course_completion_badge
    
    enrollment, _created = CourseEnrollment.objects.get_or_create(
        user=user,
        course=course,
        defaults={'status': 'enrolled'},
    )

    total_chapters = course.chapters.count()
    completed_chapters = ChapterProgress.objects.filter(
        user=user,
        chapter__course=course,
        is_complete=True,
    ).count()
    chapter_progresses = ChapterProgress.objects.filter(
        user=user,
        chapter__course=course,
    )
    if chapter_progresses.exists():
        progress_percentage = sum(item.progress_percentage for item in chapter_progresses) / chapter_progresses.count()
    else:
        progress_percentage = 0

    enrollment.completed_chapters = completed_chapters
    enrollment.total_chapters = total_chapters
    enrollment.progress_percentage = progress_percentage

    if completed_chapters == total_chapters and total_chapters > 0:
        enrollment.status = 'completed'
        enrollment.completed_date = enrollment.completed_date or timezone.now()
        
        # Award badge when course is completed ✅
        grant_course_completion_badge(user, course)
        
    elif progress_percentage > 0:
        enrollment.status = 'in_progress'
        enrollment.started_date = enrollment.started_date or timezone.now()
    else:
        enrollment.status = 'enrolled'

    enrollment.save()
    return enrollment


# ============================================================================
# COURSE VIEWSET - Full CRUD
# ============================================================================

class CourseViewSet(viewsets.ModelViewSet):
    """
    API for managing courses
    GET /api/courses/ - List courses
    GET /api/courses/{id}/ - Get course
    POST /api/courses/ - Create course
    PUT /api/courses/{id}/ - Update course
    DELETE /api/courses/{id}/ - Delete course
    POST /api/courses/{id}/enroll/ - Enroll user
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Course.objects.filter(is_published=True)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(code__icontains=search) | Q(title__icontains=search)
            )

        status_filter = self.request.query_params.get('status')
        if status_filter and self.request.user.is_authenticated:
            enrollments = CourseEnrollment.objects.filter(user=self.request.user)
            if status_filter == 'enrolled':
                queryset = queryset.filter(id__in=enrollments.values('course_id'))
            elif status_filter == 'completed':
                queryset = queryset.filter(
                    id__in=enrollments.filter(status='completed').values('course_id')
                )

        return queryset.distinct()

    def get_serializer_class(self):
        if self.action == 'list':
            return CourseListSerializer
        elif self.action in ['update', 'partial_update', 'create']:
            return CourseCreateUpdateSerializer
        else:
            return CourseDetailSerializer

    def get_object(self):
        """Allow access by both id and code"""
        queryset = self.get_queryset()
        lookup_value = self.kwargs['pk']
        try:
            return queryset.get(pk=lookup_value)
        except Course.DoesNotExist:
            return get_object_or_404(queryset, code=lookup_value)

    def perform_create(self, serializer):
        """Create new course"""
        serializer.save()

    def perform_update(self, serializer):
        """Update existing course"""
        serializer.save()

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def enroll(self, request, pk=None):
        """Enroll user in course"""
        course = self.get_object()
        user = request.user

        prerequisite_codes = get_effective_prerequisite_codes(course)
        missing_prerequisites = list(
            code for code in prerequisite_codes
            if not CourseEnrollment.objects.filter(
                user=user,
                course__code=code,
                status='completed',
            ).exists()
        )

        if missing_prerequisites:
            return Response(
                {
                    'course': ['You must complete these courses first: ' + ', '.join(missing_prerequisites)]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        enrollment, created = CourseEnrollment.objects.get_or_create(
            user=user,
            course=course,
            defaults={'status': 'enrolled'},
        )

        serializer = CourseEnrollmentSerializer(enrollment)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def enrollment_status(self, request, pk=None):
        """Return current user's enrollment for a course"""
        course = self.get_object()
        enrollment = CourseEnrollment.objects.filter(
            user=request.user,
            course=course,
        ).first()
        if not enrollment:
            return Response({'status': 'not_enrolled'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CourseEnrollmentSerializer(enrollment).data)


class CourseEnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    """List current user's course enrollments"""
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CourseEnrollment.objects.filter(user=self.request.user).order_by('-updated_at')


# ============================================================================
# CHAPTER VIEWSET - Full CRUD
# ============================================================================

class ChapterViewSet(viewsets.ModelViewSet):
    """
    API for managing chapters
    GET /api/chapters/ - List chapters
    GET /api/chapters/{id}/ - Get chapter details
    POST /api/chapters/ - Create chapter
    PUT /api/chapters/{id}/ - Update chapter
    DELETE /api/chapters/{id}/ - Delete chapter
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Chapter.objects.all()
        course_id = self.request.query_params.get('course_id')
        if course_id:
            queryset = queryset.filter(course__id=course_id)
        return queryset.order_by('order')

    def get_serializer_class(self):
        if self.action == 'list':
            return ChapterListSerializer
        elif self.action in ['update', 'partial_update', 'create']:
            return ChapterCreateUpdateSerializer
        else:
            return ChapterDetailSerializer

    def perform_create(self, serializer):
        """Create new chapter - requires course (id) in request"""
        course_id = self.request.data.get('course_id') or self.request.data.get('course')
        if not course_id:
            raise ValueError("course or course_id is required")
        course = get_object_or_404(Course, id=course_id)
        serializer.save(course=course)

    def perform_update(self, serializer):
        """Update chapter"""
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """Delete chapter"""
        return super().destroy(request, *args, **kwargs)


# ============================================================================
# LESSON VIEWSET - Full CRUD
# ============================================================================

class LessonViewSet(viewsets.ModelViewSet):
    """
    API for managing lessons
    GET /api/lessons/ - List lessons
    GET /api/lessons/{id}/ - Get lesson
    POST /api/lessons/ - Create lesson
    PUT /api/lessons/{id}/ - Update lesson
    DELETE /api/lessons/{id}/ - Delete lesson
    POST /api/lessons/{id}/mark_complete/ - Mark as complete
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Lesson.objects.all()
        chapter_id = self.request.query_params.get('chapter_id')
        if chapter_id:
            queryset = queryset.filter(chapter__id=chapter_id)
        return queryset.order_by('order')

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update', 'create']:
            return LessonCreateUpdateSerializer
        else:
            return LessonSerializer

    def perform_create(self, serializer):
        """Create new lesson - requires chapter (id) in request"""
        chapter_id = self.request.data.get('chapter_id') or self.request.data.get('chapter')
        if not chapter_id:
            raise ValueError("chapter or chapter_id is required")
        chapter = get_object_or_404(Chapter, id=chapter_id)
        serializer.save(chapter=chapter)

    def perform_update(self, serializer):
        """Update lesson"""
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """Delete lesson"""
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'])
    def mark_complete(self, request, pk=None):
        """Mark lesson as complete for user"""
        lesson = self.get_object()
        user = request.user
        if not user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        with transaction.atomic():
            progress, created = LessonProgress.objects.get_or_create(
                user=user, lesson=lesson
            )
            progress.completed = True
            progress.save()
            update_chapter_progress_for_user(user, lesson.chapter)
            update_course_enrollment_progress(user, lesson.chapter.course)

        return Response(
            {'message': 'Lesson marked as complete'},
            status=status.HTTP_200_OK
        )


# ============================================================================
# PRACTICE EXERCISE VIEWSET - Full CRUD + Submissions
# ============================================================================

class PracticeExerciseViewSet(viewsets.ModelViewSet):
    """
    API for managing practice exercises
    GET /api/practice/ - List exercises
    GET /api/practice/{id}/ - Get exercise
    POST /api/practice/ - Create exercise
    PUT /api/practice/{id}/ - Update exercise
    DELETE /api/practice/{id}/ - Delete exercise
    POST /api/practice/{id}/submit/ - Submit exercise
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = PracticeExercise.objects.all()
        chapter_id = self.request.query_params.get('chapter_id')
        if chapter_id:
            queryset = queryset.filter(chapter__id=chapter_id)
        return queryset.order_by('order')

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update', 'create']:
            return PracticeExerciseCreateUpdateSerializer
        else:
            return PracticeExerciseSerializer

    def perform_create(self, serializer):
        """Create new exercise - requires chapter (id) in request"""
        chapter_id = self.request.data.get('chapter_id') or self.request.data.get('chapter')
        if not chapter_id:
            raise ValueError("chapter or chapter_id is required")
        chapter = get_object_or_404(Chapter, id=chapter_id)
        serializer.save(chapter=chapter)

    def perform_update(self, serializer):
        """Update exercise"""
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """Delete exercise"""
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['put', 'patch'])
    def add_questions(self, request, pk=None):
        """Add or update questions for an exercise"""
        exercise = self.get_object()
        questions = request.data.get('questions', [])
        
        if not isinstance(questions, list):
            return Response(
                {'error': 'Questions must be an array'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate questions structure
        for idx, question in enumerate(questions):
            if not isinstance(question, dict):
                return Response(
                    {'error': f'Question {idx} must be an object'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if 'text' not in question and 'question' not in question:
                return Response(
                    {'error': f'Question {idx} missing text field'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if 'options' not in question:
                return Response(
                    {'error': f'Question {idx} missing options array'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if 'correctIndex' not in question and 'correctIndexes' not in question:
                return Response(
                    {'error': f'Question {idx} missing correctIndex/correctIndexes'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Replace or append questions based on request
        if request.method == 'PUT':
            exercise.questions = questions
        else:  # PATCH - append
            if exercise.questions:
                exercise.questions.extend(questions)
            else:
                exercise.questions = questions
        
        exercise.save()
        
        return Response(
            {
                'message': f'Added {len(questions)} questions',
                'total_questions': len(exercise.questions),
                'questions': exercise.questions
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit exercise answers"""
        exercise = self.get_object()
        user = request.user
        if not user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            answers = request.data.get('answers', {})
            score, _details = self._grade_answers(exercise.questions or [], answers)
            passed = score >= exercise.passing_score

            attempt = self._create_practice_attempt(
                user=user,
                exercise=exercise,
                answers=answers,
                score=score,
                passed=passed,
            )
            update_chapter_progress_for_user(user, exercise.chapter)
            update_course_enrollment_progress(user, exercise.chapter.course)

            return Response(
                {
                    'message': 'Exercise submitted',
                    'score': score,
                    'passing_score': exercise.passing_score,
                    'passed': passed,
                    'attempt_number': attempt.attempt_number,
                },
                status=status.HTTP_201_CREATED
            )
        except Exception:
            logger.error('Practice submission failed for exercise %s', pk, exc_info=True)
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @staticmethod
    def _grade_answers(questions, answers):
        """Grade a question set against submitted answers."""
        if not isinstance(questions, list):
            return 0, []

        correct = 0
        details = []

        for idx, question in enumerate(questions):
            if isinstance(answers, list):
                user_answer = answers[idx] if idx < len(answers) else None
            elif isinstance(answers, dict):
                user_answer = answers.get(str(idx), answers.get(idx))
            else:
                user_answer = None

            correct_indexes = question.get('correctIndexes')
            if correct_indexes is None:
                single_index = question.get('correctIndex')
                correct_indexes = [] if single_index is None else [single_index]
            if not correct_indexes:
                options = question.get('options', [])
                if isinstance(options, list):
                    correct_indexes = [
                        idx for idx, option in enumerate(options)
                        if isinstance(option, dict) and option.get('is_correct')
                    ]

            is_correct = False
            if user_answer is not None and correct_indexes:
                if isinstance(user_answer, list):
                    normalized_user = sorted(int(value) for value in user_answer)
                    normalized_correct = sorted(int(value) for value in correct_indexes)
                    is_correct = normalized_user == normalized_correct
                else:
                    is_correct = int(user_answer) in [int(value) for value in correct_indexes]

            if is_correct:
                correct += 1

            details.append({
                'question': idx,
                'correct': is_correct,
                'explanation': question.get('explanation', ''),
            })

        score = (correct / len(questions) * 100) if questions else 0
        return round(score, 1), details

    @staticmethod
    def _create_practice_attempt(user, exercise, answers, score, passed):
        """Create attempts with retry to avoid duplicate attempt numbers."""
        for _ in range(3):
            try:
                with transaction.atomic():
                    latest_attempt = PracticeAttempt.objects.filter(
                        user=user,
                        exercise=exercise,
                    ).aggregate(max_attempt=Max('attempt_number'))['max_attempt'] or 0

                    return PracticeAttempt.objects.create(
                        user=user,
                        exercise=exercise,
                        answers=answers,
                        score=score,
                        passed=passed,
                        attempt_number=latest_attempt + 1,
                    )
            except IntegrityError:
                continue

        raise IntegrityError('Could not assign a unique practice attempt number.')


# ============================================================================
# QUIZ VIEWSET - Full CRUD + Submissions
# ============================================================================

class QuizViewSet(viewsets.ModelViewSet):
    """
    API for managing quizzes
    GET /api/quizzes/ - List quizzes
    GET /api/quizzes/{id}/ - Get quiz
    POST /api/quizzes/ - Create quiz
    PUT /api/quizzes/{id}/ - Update quiz
    DELETE /api/quizzes/{id}/ - Delete quiz
    POST /api/quizzes/{id}/submit/ - Submit quiz
    """
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = Quiz.objects.all()
        chapter_id = self.request.query_params.get('chapter_id')
        if chapter_id:
            queryset = queryset.filter(chapter__id=chapter_id)
        return queryset.order_by('order')

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update', 'create']:
            return QuizCreateUpdateSerializer
        else:
            return QuizSerializer

    def perform_create(self, serializer):
        """Create new quiz - requires chapter (id) in request"""
        chapter_id = self.request.data.get('chapter_id') or self.request.data.get('chapter')
        if not chapter_id:
            raise ValueError("chapter or chapter_id is required")
        chapter = get_object_or_404(Chapter, id=chapter_id)
        serializer.save(chapter=chapter)

    def perform_update(self, serializer):
        """Update quiz"""
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        """Delete quiz"""
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['put', 'patch'])
    def add_questions(self, request, pk=None):
        """Add or update questions for a quiz"""
        quiz = self.get_object()
        questions = request.data.get('questions', [])
        
        if not isinstance(questions, list):
            return Response(
                {'error': 'Questions must be an array'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate questions structure
        for idx, question in enumerate(questions):
            if not isinstance(question, dict):
                return Response(
                    {'error': f'Question {idx} must be an object'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if 'text' not in question and 'question' not in question:
                return Response(
                    {'error': f'Question {idx} missing text field'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if 'options' not in question:
                return Response(
                    {'error': f'Question {idx} missing options array'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if 'correctIndex' not in question and 'correctIndexes' not in question:
                return Response(
                    {'error': f'Question {idx} missing correctIndex/correctIndexes'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Replace or append questions based on request
        if request.method == 'PUT':
            quiz.questions = questions
        else:  # PATCH - append
            if quiz.questions:
                quiz.questions.extend(questions)
            else:
                quiz.questions = questions
        
        quiz.save()
        
        return Response(
            {
                'message': f'Added {len(questions)} questions',
                'total_questions': len(quiz.questions),
                'questions': quiz.questions
            },
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit quiz with answers"""
        quiz = self.get_object()
        user = request.user
        if not user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        try:
            answers = request.data.get('answers', {})
            try:
                time_spent = int(request.data.get('time_spent', 0))
            except (TypeError, ValueError):
                time_spent = 0

            score, details = PracticeExerciseViewSet._grade_answers(quiz.questions or [], answers)
            passed = score >= quiz.passing_score

            attempt = self._create_quiz_attempt(
                user=user,
                quiz=quiz,
                answers=answers,
                score=score,
                passed=passed,
                time_spent=time_spent,
            )
            update_chapter_progress_for_user(user, quiz.chapter)
            enrollment = update_course_enrollment_progress(user, quiz.chapter.course)

            return Response(
                {
                    'message': 'Quiz submitted',
                    'score': score,
                    'passing_score': quiz.passing_score,
                    'passed': passed,
                    'attempt_number': attempt.attempt_number,
                    'details': details,
                    'course_progress_percentage': enrollment.progress_percentage,
                },
                status=status.HTTP_201_CREATED
            )
        except Exception:
            logger.error('Quiz submission failed for quiz %s', pk, exc_info=True)
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @staticmethod
    def _create_quiz_attempt(user, quiz, answers, score, passed, time_spent):
        """Create attempts with retry to avoid duplicate attempt numbers."""
        for _ in range(3):
            try:
                with transaction.atomic():
                    latest_attempt = QuizAttempt.objects.filter(
                        user=user,
                        quiz=quiz,
                    ).aggregate(max_attempt=Max('attempt_number'))['max_attempt'] or 0

                    return QuizAttempt.objects.create(
                        user=user,
                        quiz=quiz,
                        answers=answers,
                        score=score,
                        passed=passed,
                        time_spent=time_spent,
                        attempt_number=latest_attempt + 1,
                    )
            except IntegrityError:
                continue

        raise IntegrityError('Could not assign a unique quiz attempt number.')
