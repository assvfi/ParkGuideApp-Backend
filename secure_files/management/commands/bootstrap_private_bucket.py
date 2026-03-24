from django.core.management.base import BaseCommand
from secure_files.services.s3 import ensure_bucket_exists


class Command(BaseCommand):
    help = 'Create the configured private S3 bucket (if missing) and apply public access block settings.'

    def handle(self, *args, **options):
        ensure_bucket_exists()
        self.stdout.write(self.style.SUCCESS('Private S3 bucket is ready.'))
