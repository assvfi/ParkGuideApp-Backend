# courses/views.py
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from accounts.permissions import IsAdmin, IsLearner
from django.db.models import Q, F, Count
from django.utils import timezone
from .models import (
    Course, Chapter, Lesson, PracticeExercise, Quiz,
    CourseEnrollment, ChapterProgress, LessonProgress,
    PracticeAttempt, QuizAttempt,
    Module, ModuleProgress, CourseProgress
)
from .serializers import (
    CourseSerializer, CourseDetailSerializer, CourseRegistrationSerializer, CourseEnrollmentSerializer,
    CourseCreateSerializer,
    ChapterSerializer, ChapterDetailSerializer, ChapterProgressSerializer, ChapterCreateSerializer,
    LessonSerializer, LessonDetailSerializer, LessonProgressSerializer, LessonCreateSerializer,
    PracticeExerciseSerializer, PracticeAttemptSerializer, PracticeExerciseCreateSerializer,
    QuizSerializer, QuizAttemptSerializer, QuizCreateSerializer,
    ModuleSerializer, ModuleProgressSerializer, CourseProgressSerializer
)


# ============================================================================
# COURSE CATALOG & ENROLLMENT
# ============================================================================

class CourseViewSet(viewsets.ModelViewSet):
    """Course catalog with filtering"""
    queryset = Course.objects.filter(is_published=True)
    serializer_class = CourseSerializer
    permission_classes = [AllowAny]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def get_serializer_class(self):
        """Use appropriate serializer based on action"""
        if self.action in ['create', 'update', 'partial_update']:
            return CourseCreateSerializer
        elif self.action == 'retrieve':
            return CourseDetailSerializer
        return CourseSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Optional filters
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(Q(code__icontains=search) | Q(title__icontains=search))
        
        # Filter by enrollment status
        status_filter = self.request.query_params.get('status')
        if status_filter and self.request.user.is_authenticated:
            if status_filter == 'enrolled':
                enrollments = CourseEnrollment.objects.filter(user=self.request.user).values_list('course_id')
                queryset = queryset.filter(id__in=enrollments)
            elif status_filter == 'completed':
                enrollments = CourseEnrollment.objects.filter(user=self.request.user, status='completed').values_list('course_id')
                queryset = queryset.filter(id__in=enrollments)

        course_type = self.request.query_params.get('course_type')
        if course_type in ['general', 'park_specific']:
            queryset = queryset.filter(course_type=course_type)

        tag = self.request.query_params.get('tag')
        if tag:
            queryset = queryset.filter(tags__contains=[tag])
        
        return queryset.order_by('code')
    
    @action(detail=True, methods=['post'], permission_classes=[IsLearner])
    def enroll(self, request, pk=None):
        """Enroll user in course"""
        course = self.get_object()
        serializer = CourseRegistrationSerializer(
            data={'course': course.id},
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        enrollment = serializer.save()
        return Response(CourseEnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def enrollment_status(self, request, pk=None):
        """Get user's enrollment status"""
        course = self.get_object()
        try:
            enrollment = CourseEnrollment.objects.get(user=request.user, course=course)
            serializer = CourseEnrollmentSerializer(enrollment)
            return Response(serializer.data)
        except CourseEnrollment.DoesNotExist:
            return Response({'status': 'not_enrolled'}, status=status.HTTP_404_NOT_FOUND)


class CourseEnrollmentViewSet(viewsets.ReadOnlyModelViewSet):
    """User's course enrollments"""
    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsLearner]
    
    def get_queryset(self):
        return CourseEnrollment.objects.filter(user=self.request.user).select_related('course').order_by('-updated_at')


# ============================================================================
# CHAPTER VIEWS
# ============================================================================

class ChapterViewSet(viewsets.ModelViewSet):
    """Chapter details and progress"""
    queryset = Chapter.objects.all()
    serializer_class = ChapterSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def get_serializer_class(self):
        """Use CreateSerializer for write operations"""
        if self.action in ['create', 'update', 'partial_update']:
            return ChapterCreateSerializer
        return ChapterSerializer
    
    def get_queryset(self):
        course_id = self.request.query_params.get('course_id')
        if course_id:
            return Chapter.objects.filter(course_id=course_id).order_by('order')
        return Chapter.objects.all()
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to explicitly handle DELETE"""
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ============================================================================
# LESSON VIEWS
# ============================================================================

class LessonViewSet(viewsets.ModelViewSet):
    """Lesson content and progress"""
    queryset = Lesson.objects.all()
    serializer_class = LessonDetailSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        """Use CreateSerializer for write operations"""
        if self.action in ['create', 'update', 'partial_update']:
            return LessonCreateSerializer
        return LessonDetailSerializer
    
    def get_queryset(self):
        queryset = Lesson.objects.all()
        # Support nested routes (e.g., /chapters/21/lessons/)
        chapter_id = self.kwargs.get('chapter_id')
        if chapter_id:
            queryset = queryset.filter(chapter_id=chapter_id)
        # Also support query params
        query_chapter_id = self.request.query_params.get('chapter_id')
        if query_chapter_id:
            queryset = queryset.filter(chapter_id=query_chapter_id)
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        """Set chapter_id from URL parameter when creating lessons via nested route"""
        chapter_id = self.kwargs.get('chapter_id')
        
        # Just save with chapter_id from URL - serializer handles the rest
        if chapter_id:
            serializer.save(chapter_id=chapter_id)
        else:
            serializer.save()
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to explicitly handle DELETE"""
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'], permission_classes=[IsLearner])
    def mark_complete(self, request, pk=None):
        """Mark lesson as completed"""
        lesson = self.get_object()
        time_spent = request.data.get('time_spent', 0)
        
        progress, created = LessonProgress.objects.update_or_create(
            user=request.user,
            lesson=lesson,
            defaults={'completed': True, 'time_spent': time_spent, 'completed_at': timezone.now()}
        )
        
        # Update chapter progress
        self._update_chapter_progress(lesson.chapter)
        
        serializer = LessonProgressSerializer(progress)
        return Response(serializer.data)
    
    @staticmethod
    def _update_chapter_progress(chapter):
        """Recalculate chapter progress"""
        print(f"[_update_chapter_progress] Updating progress for chapter {chapter.id}: {chapter.title}")
        
        for enrollment in CourseEnrollment.objects.filter(course=chapter.course):
            print(f"[_update_chapter_progress]   Processing user: {enrollment.user.id}")
            
            lessons = chapter.lessons.all()
            print(f"[_update_chapter_progress]   Total lessons in chapter: {lessons.count()}")
            
            completed = LessonProgress.objects.filter(
                user=enrollment.user,
                lesson__in=lessons,
                completed=True
            ).count()
            print(f"[_update_chapter_progress]   Completed lessons: {completed}")
            
            total = lessons.count()
            
            # Determine what components exist in this chapter
            has_practice = chapter.practice_exercises.exists()
            has_quiz = chapter.quizzes.exists()
            
            # Count actual components to redistribute percentages if some don't exist
            component_count = 1  # Lessons always count
            if has_practice:
                component_count += 1
            if has_quiz:
                component_count += 1
            
            # Calculate percentage per component
            pct_per_component = 100 / component_count
            
            # Calculate base progress for lessons
            lessons_progress = (completed / total * pct_per_component) if total > 0 else 0
            print(f"[_update_chapter_progress]   Lessons progress: {lessons_progress}%")
            
            # Check if practice passed
            practice_pct = 0
            practice_passed = False
            
            if has_practice:
                practice = chapter.practice_exercises.first()
                best_attempt = PracticeAttempt.objects.filter(
                    user=enrollment.user,
                    exercise=practice
                ).order_by('-score').first()
                if best_attempt and best_attempt.passed:
                    practice_pct = pct_per_component
                    practice_passed = True
            else:
                # If no practice exercise exists, auto-pass it and add its percentage
                practice_pct = pct_per_component
                practice_passed = True
            print(f"[_update_chapter_progress]   Practice exists: {has_practice}, passed: {practice_passed}, pct: {practice_pct}%")
            
            # Check if quiz passed
            quiz_pct = 0
            quiz_passed = False
            
            if has_quiz:
                quiz = chapter.quizzes.first()
                best_attempt = QuizAttempt.objects.filter(
                    user=enrollment.user,
                    quiz=quiz
                ).order_by('-score').first()
                if best_attempt and best_attempt.passed:
                    quiz_pct = pct_per_component
                    quiz_passed = True
            else:
                # If no quiz exists, auto-pass it and add its percentage
                quiz_pct = pct_per_component
                quiz_passed = True
            print(f"[_update_chapter_progress]   Quiz exists: {has_quiz}, passed: {quiz_passed}, pct: {quiz_pct}%")
            
            # Calculate total progress: always cap at 100%
            total_progress = min(100, lessons_progress + practice_pct + quiz_pct)
            
            # Chapter is complete only if:
            # - All lessons are completed (if any exist)
            # - Practice is passed (if it exists) 
            # - Quiz is passed (if it exists)
            is_complete = completed == total and practice_passed and quiz_passed
            print(f"[_update_chapter_progress]   Total progress: {total_progress}%, Complete: {is_complete}")
            
            ChapterProgress.objects.update_or_create(
                user=enrollment.user,
                chapter=chapter,
                defaults={
                    'completed_lessons': completed,
                    'total_lessons': total,
                    'practice_completed': practice_passed,
                    'practice_score': best_attempt.score if has_practice and best_attempt else None,
                    'quiz_completed': quiz_passed,
                    'quiz_score': best_attempt.score if has_quiz and best_attempt else None,
                    'quiz_passed': quiz_passed,
                    'progress_percentage': total_progress,
                    'is_complete': is_complete
                }
            )
        
        # After updating all chapter progress, update the course enrollment progress
        LessonViewSet._update_course_enrollment_progress(chapter.course)

    @staticmethod
    def _update_course_enrollment_progress(course):
        """Update CourseEnrollment progress based on completed chapters"""
        # Get total chapters for this course
        total_chapters = course.chapters.count()
        
        # For each user enrolled in this course
        for enrollment in CourseEnrollment.objects.filter(course=course):
            # Count completed chapters for this user
            completed_chapters = ChapterProgress.objects.filter(
                user=enrollment.user,
                chapter__course=course,
                is_complete=True
            ).count()
            
            # Update enrollment progress
            progress_percentage = (completed_chapters / total_chapters * 100) if total_chapters > 0 else 0
            enrollment.completed_chapters = completed_chapters
            enrollment.total_chapters = total_chapters
            enrollment.progress_percentage = progress_percentage
            
            # Auto-update status based on progress
            if progress_percentage >= 100 and completed_chapters == total_chapters:
                enrollment.status = 'completed'
            elif progress_percentage > 0:
                enrollment.status = 'in_progress'
            
            enrollment.save()
            print(f"[_update_course_enrollment_progress] {enrollment.user.username} - {course.code}: {completed_chapters}/{total_chapters} ({progress_percentage:.1f}%)")


# ============================================================================
# PRACTICE VIEWS
# ============================================================================

class PracticeExerciseViewSet(viewsets.ModelViewSet):
    """Practice exercises"""
    queryset = PracticeExercise.objects.all()
    serializer_class = PracticeExerciseSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        """Use CreateSerializer for write operations"""
        if self.action in ['create', 'update', 'partial_update']:
            return PracticeExerciseCreateSerializer
        return PracticeExerciseSerializer
    
    def get_queryset(self):
        queryset = PracticeExercise.objects.all()
        # Support nested routes (e.g., /chapters/21/exercises/)
        chapter_id = self.kwargs.get('chapter_id')
        if chapter_id:
            queryset = queryset.filter(chapter_id=chapter_id)
        # Also support query params
        query_chapter_id = self.request.query_params.get('chapter_id')
        if query_chapter_id:
            queryset = queryset.filter(chapter_id=query_chapter_id)
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        """Set chapter_id from URL parameter when creating exercises via nested route"""
        chapter_id = self.kwargs.get('chapter_id')
        
        # Just save with chapter_id from URL - serializer handles the rest
        if chapter_id:
            serializer.save(chapter_id=chapter_id)
        else:
            serializer.save()
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to explicitly handle DELETE"""
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'], permission_classes=[IsLearner])
    def submit(self, request, pk=None):
        """Submit practice answers"""
        exercise = self.get_object()
        answers = request.data.get('answers', {})
        
        # Grade the practice
        score, details = self._grade_answers(exercise, answers)
        passed = score >= exercise.passing_score
        
        attempt = PracticeAttempt.objects.create(
            user=request.user,
            exercise=exercise,
            answers=answers,
            score=score,
            passed=passed,
            attempt_number=PracticeAttempt.objects.filter(
                user=request.user,
                exercise=exercise
            ).count() + 1
        )
        
        # Update chapter progress
        LessonViewSet._update_chapter_progress(exercise.chapter)
        
        serializer = PracticeAttemptSerializer(attempt)
        return Response({
            **serializer.data,
            'details': details,
            'message': 'Congratulations! You passed.' if passed else 'Try again to improve your score.'
        })
    
    @staticmethod
    def _grade_answers(exercise, answers):
        """Auto-grade practice answers"""
        questions = exercise.questions
        if not isinstance(questions, list):
            questions = [questions] if questions else []
        
        # Convert array answers to dict format (frontend sends array, backend expects dict)
        if isinstance(answers, list):
            answers_dict = {str(idx): ans for idx, ans in enumerate(answers)}
        else:
            answers_dict = answers
        
        correct = 0
        details = []
        
        for idx, question in enumerate(questions):
            user_answer = answers_dict.get(str(idx))
            
            # Find correct answer index from the question
            # Supports two formats:
            # 1. New format: options have is_correct flag
            # 2. Old format: question has correctIndex or correctIndexes field
            correct_answer_indices = []
            
            # Check new format (options with is_correct flag)
            if isinstance(question.get('options'), list):
                for opt_idx, option in enumerate(question['options']):
                    if isinstance(option, dict) and option.get('is_correct', False):
                        correct_answer_indices.append(opt_idx)
            
            # Fallback to old format if no correct answer found
            if not correct_answer_indices:
                correct_answer = question.get('correctIndexes', [question.get('correctIndex')])
                if isinstance(correct_answer, list):
                    correct_answer_indices = correct_answer
                else:
                    correct_answer_indices = [correct_answer] if correct_answer is not None else []
            
            # Compare user answer with correct answer
            is_correct = False
            if correct_answer_indices:
                if isinstance(user_answer, list):
                    is_correct = sorted(user_answer) == sorted(correct_answer_indices)
                else:
                    is_correct = user_answer in correct_answer_indices
            
            if is_correct:
                correct += 1
            
            details.append({
                'question': idx,
                'correct': is_correct,
                'explanation': question.get('explanation', '')
            })
        
        score = (correct / len(questions) * 100) if questions else 0
        return round(score, 1), details


# ============================================================================
# QUIZ VIEWS
# ============================================================================

class QuizViewSet(viewsets.ModelViewSet):
    """Quiz interface"""
    queryset = Quiz.objects.all()
    serializer_class = QuizSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdmin()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        """Use CreateSerializer for write operations"""
        if self.action in ['create', 'update', 'partial_update']:
            return QuizCreateSerializer
        return QuizSerializer
    
    def get_queryset(self):
        queryset = Quiz.objects.all()
        # Support nested routes (e.g., /chapters/21/quizzes/)
        chapter_id = self.kwargs.get('chapter_id')
        if chapter_id:
            queryset = queryset.filter(chapter_id=chapter_id)
        # Also support query params
        query_chapter_id = self.request.query_params.get('chapter_id')
        if query_chapter_id:
            queryset = queryset.filter(chapter_id=query_chapter_id)
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        """Set chapter_id from URL parameter when creating quizzes via nested route"""
        chapter_id = self.kwargs.get('chapter_id')
        
        # Just save with chapter_id from URL - serializer handles the rest
        if chapter_id:
            serializer.save(chapter_id=chapter_id)
        else:
            serializer.save()
    
    def destroy(self, request, *args, **kwargs):
        """Override destroy to explicitly handle DELETE"""
        instance = self.get_object()
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'], permission_classes=[IsLearner])
    def submit(self, request, pk=None):
        """Submit quiz"""
        quiz = self.get_object()
        answers = request.data.get('answers', [])
        time_spent = request.data.get('time_spent', 0)
        
        try:
            # Validate quiz has questions
            if not quiz.questions or not isinstance(quiz.questions, list):
                return Response(
                    {'error': 'Quiz questions are not properly configured'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Grade the quiz with error handling
            try:
                score, details = PracticeExerciseViewSet._grade_answers(quiz, answers)
            except Exception as e:
                print(f"[QuizViewSet] Error grading quiz {pk}: {str(e)}")
                return Response(
                    {'error': f'Error grading quiz: {str(e)}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            passed = score >= quiz.passing_score
            
            attempt = QuizAttempt.objects.create(
                user=request.user,
                quiz=quiz,
                answers=answers,
                score=score,
                passed=passed,
                time_spent=time_spent,
                attempt_number=QuizAttempt.objects.filter(
                    user=request.user,
                    quiz=quiz
                ).count() + 1
            )
            
            # Update chapter progress
            LessonViewSet._update_chapter_progress(quiz.chapter)
            
            # Update course enrollment - use get_or_create to avoid crashes
            course_enrollment, created = CourseEnrollment.objects.get_or_create(
                user=request.user,
                course=quiz.chapter.course,
                defaults={'status': 'in_progress'}
            )
            
            total_chapters = quiz.chapter.course.chapters.count()
            completed_chapters = ChapterProgress.objects.filter(
                user=request.user,
                chapter__course=quiz.chapter.course,
                is_complete=True
            ).count()
            
            progress_pct = (completed_chapters / total_chapters * 100) if total_chapters > 0 else 0
            
            if completed_chapters == total_chapters:
                course_enrollment.status = 'completed'
                course_enrollment.completed_date = timezone.now()
                course_enrollment.final_score = progress_pct
            else:
                course_enrollment.status = 'in_progress'
            
            course_enrollment.progress_percentage = progress_pct
            course_enrollment.save()
            
            serializer = QuizAttemptSerializer(attempt)
            response_data = {
                **serializer.data,
                'details': details,
            }
            
            if passed:
                response_data['message'] = 'Passed! Chapter complete.'
                if completed_chapters == total_chapters:
                    response_data['course_completed'] = True
                    response_data['course_message'] = 'Congratulations! You completed the course!'
            else:
                response_data['message'] = f'Score: {score}%. Need {quiz.passing_score}% to pass.'
            
            return Response(response_data)
            
        except Exception as e:
            print(f"[QuizViewSet] Unexpected error in submit: {str(e)}")
            import traceback
            traceback.print_exc()
            return Response(
                {'error': f'Server error: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ============================================================================
# LEGACY VIEWS (backwards compatibility)
# ============================================================================

class ModuleViewSet(viewsets.ModelViewSet):
    """Legacy module view"""
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [IsAuthenticated]


class ModuleProgressViewSet(viewsets.ModelViewSet):
    """Legacy module progress view"""
    serializer_class = ModuleProgressSerializer
    permission_classes = [IsLearner]

    def get_queryset(self):
        return ModuleProgress.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        module = serializer.validated_data['module']
        completed = serializer.validated_data.get('completed', False)

        progress, created = ModuleProgress.objects.update_or_create(
            user=request.user,
            module=module,
            defaults={'completed': completed},
        )

        output_serializer = self.get_serializer(progress)
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(output_serializer.data, status=response_status)


class CourseProgressViewSet(viewsets.ModelViewSet):
    """Legacy course progress view"""
    serializer_class = CourseProgressSerializer
    permission_classes = [IsLearner]

    def get_queryset(self):
        return CourseProgress.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        course = serializer.validated_data['course']
        progress, created = CourseProgress.objects.update_or_create(
            user=request.user,
            course=course,
            defaults={
                'completed_modules': serializer.validated_data.get('completed_modules', 0),
                'total_modules': serializer.validated_data.get('total_modules', 0),
                'progress': serializer.validated_data.get('progress', 0),
                'completed': serializer.validated_data.get('completed', False),
            },
        )

        output_serializer = self.get_serializer(progress)
        response_status = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(output_serializer.data, status=response_status)


class CompleteModuleView(APIView):
    """Legacy module completion endpoint"""
    permission_classes = [IsLearner]

    def post(self, request):
        module_id = request.data.get('module_id')

        try:
            module = Module.objects.select_related('course').get(id=module_id)
        except Module.DoesNotExist:
            return Response({'detail': 'Invalid module_id'}, status=status.HTTP_400_BAD_REQUEST)

        progress, created = ModuleProgress.objects.get_or_create(
            user=request.user,
            module=module,
            defaults={'completed': True}
        )

        if not created and not progress.completed:
            progress.completed = True
            progress.save(update_fields=['completed'])

        course = module.course
        total_modules = course.modules.count()
        completed_modules = ModuleProgress.objects.filter(
            user=request.user,
            module__course=course,
            completed=True,
        ).count()
        ratio = (completed_modules / total_modules) if total_modules else 0

        CourseProgress.objects.update_or_create(
            user=request.user,
            course=course,
            defaults={
                'completed_modules': completed_modules,
                'total_modules': total_modules,
                'progress': ratio,
                'completed': total_modules > 0 and completed_modules >= total_modules,
            }
        )

        return Response({'status': 'completed', 'created': created})
