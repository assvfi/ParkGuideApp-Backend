# courses/views.py
from rest_framework import viewsets, permissions, status
from .models import Course, Module
from .serializers import CourseSerializer, ModuleSerializer
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import ModuleProgress, CourseProgress
from .serializers import ModuleProgressSerializer, CourseProgressSerializer

class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]  # requires token

class ModuleViewSet(viewsets.ModelViewSet):
    queryset = Module.objects.all()
    serializer_class = ModuleSerializer
    permission_classes = [permissions.IsAuthenticated]


class ModuleProgressViewSet(viewsets.ModelViewSet):
    serializer_class = ModuleProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

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
    serializer_class = CourseProgressSerializer
    permission_classes = [permissions.IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

    def post(self,request):
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