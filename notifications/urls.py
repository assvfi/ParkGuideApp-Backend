from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import UserNotificationViewSet

router = DefaultRouter()
router.register(r'items', UserNotificationViewSet, basename='notification-item')

urlpatterns = [
    path('', include(router.urls)),
]
