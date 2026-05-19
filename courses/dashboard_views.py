# courses/dashboard_views.py
"""
Dashboard REST API views for user progress tracking and analytics
These views provide comprehensive endpoints for dashboard functionality.
"""

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count, Q, Avg, Sum, F, Max
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator

from accounts.models import CustomUser
from accounts.permissions import IsAdmin
from .models import (
    Course, Chapter, CourseEnrollment, ChapterProgress, LessonProgress,
    PracticeAttempt, QuizAttempt
)
from .dashboard_serializers import (
    UserProgressSummarySerializer, CourseProgressDetailSerializer,
    ChapterProgressDetailSerializer, DashboardOverviewSerializer,
    UserLeaderboardEntry, CourseCatalogStatsSerializer,
    UserLearningStatsSerializer
)

User = get_user_model()


class UserProgressViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for user progress tracking
    
    Endpoints:
    - GET /api/dashboard/user-progress/ - Get current user's progress summary
    - GET /api/dashboard/user-progress/{id}/ - Get specific user's progress (admin only)
    - GET /api/dashboard/user-progress/?format=summary - Get all users progress (paginated, admin only)
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProgressSummarySerializer
    
    def get_queryset(self):
        """Filter based on user permissions"""
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return User.objects.all()
        return User.objects.filter(id=user.id)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_progress(self, request):
        """
        Get current user's progress summary
        GET /api/dashboard/user-progress/my_progress/
        """
        user = request.user
        data = self._get_user_progress_data(user)
        serializer = UserProgressSummarySerializer(data)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAdmin])
    def summary(self, request):
        """
        Get paginated list of all users' progress (admin only)
        GET /api/dashboard/user-progress/summary/?page=1&page_size=20
        """
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        
        users = User.objects.all().order_by('-last_login')
        paginator = Paginator(users, page_size)
        page_obj = paginator.get_page(page)
        
        data_list = [self._get_user_progress_data(user) for user in page_obj]
        serializer = UserProgressSummarySerializer(data_list, many=True)
        
        return Response({
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page,
            'page_size': page_size,
            'results': serializer.data
        })
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def courses(self, request, pk=None):
        """
        Get detailed progress for all courses of a user
        GET /api/dashboard/user-progress/{user_id}/courses/
        """
        target_user = self.get_object()
        
        # Check permissions
        if target_user.id != request.user.id and not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {'error': 'You do not have permission to view this user\'s data'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        enrollments = CourseEnrollment.objects.filter(user=target_user).order_by('-updated_at')
        serializer = CourseProgressDetailSerializer(enrollments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def chapter_details(self, request, pk=None):
        """
        Get detailed progress for all chapters of a user
        GET /api/dashboard/user-progress/{user_id}/chapter_details/
        """
        target_user = self.get_object()
        
        # Check permissions
        if target_user.id != request.user.id and not (request.user.is_staff or request.user.is_superuser):
            return Response(
                {'error': 'You do not have permission to view this user\'s data'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        course_id = request.query_params.get('course_id')
        
        query = ChapterProgress.objects.filter(user=target_user).order_by('-updated_at')
        if course_id:
            query = query.filter(chapter__course_id=course_id)
        
        serializer = ChapterProgressDetailSerializer(query, many=True)
        return Response(serializer.data)
    
    def _get_user_progress_data(self, user):
        """
        Aggregate user progress data
        """
        enrollments = CourseEnrollment.objects.filter(user=user)
        
        total_courses_enrolled = enrollments.count()
        total_courses_completed = enrollments.filter(status='completed').count()
        
        chapter_progress = ChapterProgress.objects.filter(user=user)
        total_chapters_completed = chapter_progress.filter(is_complete=True).count()
        
        lesson_progress = LessonProgress.objects.filter(user=user, completed=True)
        total_lessons_completed = lesson_progress.count()
        
        quiz_attempts = QuizAttempt.objects.filter(user=user, passed=True)
        total_quizzes_passed = quiz_attempts.count()
        
        # Calculate averages
        avg_enrollment_progress = enrollments.aggregate(avg=Avg('progress_percentage'))['avg'] or 0
        
        quiz_scores = QuizAttempt.objects.filter(user=user).aggregate(avg=Avg('score'))['avg'] or 0
        
        # Calculate total learning time (time spent on lessons + quiz time)
        lesson_time = lesson_progress.aggregate(total=Sum('time_spent'))['total'] or 0
        quiz_time = quiz_attempts.aggregate(total=Sum('time_spent'))['total'] or 0
        total_learning_time = lesson_time + quiz_time
        
        return {
            'user_id': user.id,
            'email': user.email,
            'username': user.username,
            'total_courses_enrolled': total_courses_enrolled,
            'total_courses_completed': total_courses_completed,
            'total_chapters_completed': total_chapters_completed,
            'total_lessons_completed': total_lessons_completed,
            'total_quizzes_passed': total_quizzes_passed,
            'average_course_progress': avg_enrollment_progress,
            'average_course_score': quiz_scores,
            'total_learning_time': total_learning_time,
        }


class DashboardStatsView(APIView):
    """
    Overall dashboard statistics

    GET /api/dashboard/stats/overview/ - Get overview statistics
    GET /api/dashboard/stats/leaderboard/ - Get user leaderboard
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        """Get dashboard overview"""
        # Catalog stats
        courses_total = Course.objects.count()
        courses_published = Course.objects.filter(is_published=True).count()
        chapters_total = Course.objects.aggregate(total=Count('chapters'))['total'] or 0
        lessons_total = Course.objects.aggregate(total=Count('chapters__lessons'))['total'] or 0
        quizzes_total = Course.objects.aggregate(total=Count('chapters__quizzes'))['total'] or 0
        
        catalog_stats = {
            'total_courses': courses_total,
            'published_courses': courses_published,
            'total_chapters': chapters_total,
            'total_lessons': lessons_total,
            'total_quizzes': quizzes_total,
        }
        
        # User activity stats
        user_count = User.objects.filter(user_type='learner').count()
        
        one_week_ago = timezone.now() - timezone.timedelta(days=7)
        active_users_this_week = User.objects.filter(
            user_type='learner',
            last_login__gte=one_week_ago
        ).count()
        
        # Enrollment stats
        total_enrollments = CourseEnrollment.objects.count()
        active_enrollments = CourseEnrollment.objects.filter(
            status__in=['enrolled', 'in_progress']
        ).count()
        completed_enrollments = CourseEnrollment.objects.filter(status='completed').count()
        
        data = {
            'catalog_stats': catalog_stats,
            'user_count': user_count,
            'active_users_this_week': active_users_this_week,
            'total_enrollments': total_enrollments,
            'active_enrollments': active_enrollments,
            'completed_enrollments': completed_enrollments,
        }
        
        serializer = DashboardOverviewSerializer(data)
        return Response(serializer.data)


class LeaderboardView(APIView):
    """
    User leaderboard based on learning achievements

    GET /api/dashboard/leaderboard/?metric=courses_completed&limit=20
    Metrics: courses_completed, avg_score, learning_time, quizzes_passed
    """
    permission_classes = [IsAdmin]

    def get(self, request):
        """Get leaderboard"""
        metric = request.query_params.get('metric', 'courses_completed')
        limit = int(request.query_params.get('limit', 20))
        
        leaderboard = self._build_leaderboard(metric, limit)
        
        data_list = [
            {
                'rank': idx + 1,
                'user_id': entry['user_id'],
                'email': entry['email'],
                'username': entry['username'],
                'courses_completed': entry['courses_completed'],
                'quizzes_passed': entry['quizzes_passed'],
                'average_score': entry['average_score'],
                'total_learning_time': entry['total_learning_time'],
                'badges_earned': entry['badges_earned'],
                'last_activity': entry['last_activity'],
            }
            for idx, entry in enumerate(leaderboard)
        ]
        
        serializer = UserLeaderboardEntry(data_list, many=True)
        return Response({
            'metric': metric,
            'count': len(leaderboard),
            'results': serializer.data
        })
    
    def _build_leaderboard(self, metric, limit):
        """Build leaderboard based on metric"""
        users = User.objects.filter(user_type='learner')
        
        leaderboard_data = []
        
        for user in users:
            courses_completed = CourseEnrollment.objects.filter(
                user=user, status='completed'
            ).count()
            
            quizzes_passed = QuizAttempt.objects.filter(user=user, passed=True).count()
            
            avg_score = QuizAttempt.objects.filter(user=user).aggregate(
                avg=Avg('score')
            )['avg'] or 0
            
            total_learning_time = (
                LessonProgress.objects.filter(user=user, completed=True).aggregate(
                    total=Sum('time_spent')
                )['total'] or 0
            ) + (
                QuizAttempt.objects.filter(user=user).aggregate(
                    total=Sum('time_spent')
                )['total'] or 0
            )
            
            # For now, badges earned is 0 (can be extended later)
            badges_earned = 0
            
            leaderboard_data.append({
                'user_id': user.id,
                'email': user.email,
                'username': user.username,
                'courses_completed': courses_completed,
                'quizzes_passed': quizzes_passed,
                'average_score': round(avg_score, 2),
                'total_learning_time': total_learning_time,
                'badges_earned': badges_earned,
                'last_activity': user.last_login,
                'sort_value': self._get_sort_value(metric, {
                    'courses_completed': courses_completed,
                    'average_score': avg_score,
                    'total_learning_time': total_learning_time,
                    'quizzes_passed': quizzes_passed,
                })
            })
        
        # Sort and limit
        leaderboard_data.sort(key=lambda x: x['sort_value'], reverse=True)
        return leaderboard_data[:limit]
    
    def _get_sort_value(self, metric, values):
        """Get sort value based on metric"""
        metric_map = {
            'courses_completed': 'courses_completed',
            'avg_score': 'average_score',
            'learning_time': 'total_learning_time',
            'quizzes_passed': 'quizzes_passed',
        }
        return values.get(metric_map.get(metric, 'courses_completed'), 0)


class SpoofProgressView(APIView):
    """
    Admin-only endpoint to spoof progress/enrollment for testing.

    POST payload (JSON):
    - users: [user_id, ...] OR
    - emails: [email, ...] OR
    - all: true
    - course_id: optional int to target a specific course
    - action: 'complete' | 'reset' | 'partial'  (default 'complete')
    - progress: float between 0-100 (used for 'partial')
    - score: float (optional final score)
    """
    permission_classes = [IsAdmin]

    def post(self, request):
        payload = request.data or {}
        user_ids = payload.get('users')
        emails = payload.get('emails')
        apply_all = payload.get('all', False)
        course_id = payload.get('course_id')
        action = payload.get('action', 'complete')
        progress_value = float(payload.get('progress', 100))
        score_value = payload.get('score', 100)

        users_qs = None
        if apply_all:
            users_qs = User.objects.filter(user_type='learner')
        elif user_ids:
            users_qs = User.objects.filter(id__in=user_ids)
        elif emails:
            users_qs = User.objects.filter(email__in=emails)
        else:
            return Response({'error': 'No target users specified'}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        affected = {'enrollments_updated': 0, 'chapter_progress_created': 0}
        from django.db import transaction

        with transaction.atomic():
            for user in users_qs:
                enrollments = CourseEnrollment.objects.filter(user=user)
                if course_id:
                    enrollments = enrollments.filter(course_id=course_id)

                for enroll in enrollments:
                    # ensure total_chapters is set
                    total_chapters = enroll.total_chapters or enroll.course.chapters.count()
                    enroll.total_chapters = total_chapters

                    if action == 'reset':
                        enroll.status = 'enrolled'
                        enroll.completed_chapters = 0
                        enroll.progress_percentage = 0
                        enroll.completed_date = None
                        enroll.final_score = None
                        enroll.save()
                        affected['enrollments_updated'] += 1
                        continue

                    if action == 'partial':
                        # set a partial progress
                        percent = max(0.0, min(100.0, progress_value))
                        enroll.progress_percentage = percent
                        enroll.completed_chapters = int(round((percent / 100.0) * total_chapters))
                        enroll.status = 'in_progress' if percent < 100 else 'completed'
                        if percent >= 100:
                            enroll.completed_date = now
                            enroll.final_score = score_value
                        enroll.save()
                        affected['enrollments_updated'] += 1
                    else:
                        # default: mark complete
                        enroll.completed_chapters = total_chapters
                        enroll.progress_percentage = 100
                        enroll.status = 'completed'
                        enroll.completed_date = now
                        enroll.final_score = score_value
                        enroll.save()
                        affected['enrollments_updated'] += 1

                        # create/update chapter progress for all chapters
                        chapters = enroll.course.chapters.all()
                        for chapter in chapters:
                            cp, created = ChapterProgress.objects.update_or_create(
                                user=user,
                                chapter=chapter,
                                defaults={
                                    'completed_lessons': chapter.lessons.count(),
                                    'total_lessons': chapter.lessons.count() or 0,
                                    'practice_completed': True,
                                    'practice_score': 100,
                                    'practice_passed': True,
                                    'quiz_completed': True,
                                    'quiz_score': 100,
                                    'quiz_passed': True,
                                    'progress_percentage': 100,
                                    'is_complete': True,
                                    'completed_at': now,
                                    'started_at': now,
                                }
                            )
                            if created:
                                affected['chapter_progress_created'] += 1

                            # mark lessons complete for the chapter
                            for lesson in chapter.lessons.all():
                                LessonProgress.objects.update_or_create(
                                    user=user,
                                    lesson=lesson,
                                    defaults={
                                        'completed': True,
                                        'time_spent': 60,
                                        'completed_at': now,
                                    }
                                )

                        # create a synthetic quiz attempt (optional)
                        try:
                            QuizAttempt.objects.create(
                                user=user,
                                quiz=enroll.course.chapters.first().quizzes.first() if enroll.course.chapters.exists() and enroll.course.chapters.first().quizzes.exists() else None,
                                attempt_number=1,
                                answers={},
                                score=score_value or 100,
                                passed=True,
                                time_spent=30,
                            )
                        except Exception:
                            # ignore if no quiz exists or required fields missing
                            pass

        return Response({'status': 'ok', 'summary': affected})
