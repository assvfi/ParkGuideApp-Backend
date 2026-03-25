import datetime
import firebase_admin
from firebase_admin import credentials, storage
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from ..models import SecureFile

# Initialize Firebase App (Ensure this is called once, e.g., in apps.py ready())
if not firebase_admin._apps:
    cred = credentials.Certificate(settings.FIREBASE_SERVICE_ACCOUNT_PATH)
    firebase_admin.initialize_app(cred, {
        'storageBucket': settings.FIREBASE_STORAGE_BUCKET
    })

def upload_file(uploaded, owner):
    bucket = storage.bucket()
    # Generate a unique path/blob name
    blob_path = f"uploads/{owner.id}/{datetime.datetime.now().timestamp()}_{uploaded.name}"
    blob = bucket.blob(blob_path)
    
    # Upload from the file-like object
    blob.upload_from_file(uploaded, content_type=uploaded.content_type)
    
    # Create the DB record (keeping s3_key as the path reference)
    return SecureFile.objects.create(
        owner=owner,
        original_name=uploaded.name,
        s3_key=blob_path, # We reuse this field for the Firebase path
        content_type=uploaded.content_type,
        size=uploaded.size
    )

def generate_download_url(blob_path):
    bucket = storage.bucket()
    blob = bucket.blob(blob_path)
    # Generate a signed URL valid for 1 hour
    return blob.generate_signed_url(datetime.timedelta(seconds=3600), method='GET')

def delete_file(blob_path):
    bucket = storage.bucket()
    blob = bucket.blob(blob_path)
    blob.delete()

def download_file_bytes(blob_path):
    bucket = storage.bucket()
    blob = bucket.blob(blob_path)
    return blob.download_as_bytes(), blob.content_type