from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import UserNotificationViewSet, PushTokenViewSet

router = DefaultRouter()
router.register(r'items', UserNotificationViewSet, basename='notification-item')
router.register(r'push-tokens', PushTokenViewSet, basename='push-token')

urlpatterns = [
    path('', include(router.urls)),
]
