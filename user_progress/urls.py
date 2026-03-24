from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import BadgeViewSet, MyBadgeViewSet

router = DefaultRouter()
router.register(r'badges', BadgeViewSet, basename='badge')
router.register(r'my-badges', MyBadgeViewSet, basename='my-badge')

urlpatterns = [
    path('', include(router.urls)),
]
