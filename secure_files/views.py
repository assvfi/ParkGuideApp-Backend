from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse

from .models import SecureFile
from .serializers import SecureFileSerializer
from .services.firebase_storage import delete_file, download_file_bytes, generate_download_url, upload_file


class SecureFileViewSet(viewsets.ModelViewSet):
    serializer_class = SecureFileSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        # For study-material use, authenticated users can read all uploaded files.
        # Write/delete restrictions are enforced separately.
        return SecureFile.objects.all()

    def perform_create(self, serializer):
        raise NotImplementedError('Use create override for file uploads.')

    def create(self, request, *args, **kwargs):
        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'detail': 'Missing file field.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            secure_file = upload_file(uploaded=uploaded, owner=request.user)
        except ImproperlyConfigured as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        data = self.get_serializer(secure_file).data
        return Response(data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        secure_file = self.get_object()
        if not request.user.is_staff and secure_file.owner_id != request.user.id:
            return Response({'detail': 'You do not have permission to delete this file.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            delete_file(secure_file.s3_key)
        except ImproperlyConfigured as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        secure_file.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'], url_path='download-url')
    def download_url(self, request, pk=None):
        secure_file = self.get_object()
        try:
            url = generate_download_url(secure_file.s3_key)
        except ImproperlyConfigured as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'download_url': url})

    @action(detail=True, methods=['get'], url_path='download')
    def download(self, request, pk=None):
        secure_file = self.get_object()

        try:
            file_bytes, content_type = download_file_bytes(secure_file.s3_key)
        except ImproperlyConfigured as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        response = HttpResponse(file_bytes, content_type=content_type)
        response['Content-Disposition'] = f'inline; filename="{secure_file.original_name}"'
        return response
