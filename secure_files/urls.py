from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import SecureFileViewSet

router = DefaultRouter()
router.register(r'files', SecureFileViewSet, basename='secure-file')

urlpatterns = [
    path('', include(router.urls)),
]
