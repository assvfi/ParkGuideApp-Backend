from django.core.management.base import BaseCommand
# Change the import to your new Firebase service
from secure_files.services.firebase_storage import storage 

class Command(BaseCommand):
    help = 'Verify connection to the configured Firebase Storage bucket.'

    def handle(self, *args, **options):
        try:
            # We try to get the bucket metadata to verify connection/permissions
            bucket = storage.bucket()
            if bucket.exists():
                self.stdout.write(self.style.SUCCESS(f'Firebase bucket "{bucket.name}" is accessible.'))
            else:
                self.stdout.write(self.style.ERROR(f'Bucket "{bucket.name}" does not exist. Check your FIREBASE_STORAGE_BUCKET setting.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to connect to Firebase: {e}'))