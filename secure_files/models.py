from django.conf import settings
from django.db import models


class SecureFile(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='secure_files')
    original_name = models.CharField(max_length=255)
    s3_key = models.CharField(max_length=500, unique=True)
    content_type = models.CharField(max_length=255, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-uploaded_at',)

    def __str__(self):
        return f"{self.owner} - {self.original_name}"
