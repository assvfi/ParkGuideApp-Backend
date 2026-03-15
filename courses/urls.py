from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CourseViewSet, ModuleViewSet

router = DefaultRouter()
router.register(r'courses', CourseViewSet)
router.register(r'modules', ModuleViewSet)

urlpatterns = [
    path('', include(router.urls)),
]