import os
import uuid
from datetime import datetime

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from secure_files.models import SecureFile

try:
    import boto3
    from botocore.exceptions import ClientError
except Exception:
    boto3 = None
    ClientError = Exception


def _require_boto3():
    if boto3 is None:
        raise ImproperlyConfigured('boto3 is not installed. Install boto3 to use S3-backed file storage.')


def _require_s3_config():
    if not settings.S3_ENABLED:
        raise ImproperlyConfigured('S3 storage is disabled. Set S3_ENABLED=true to use secure files.')
    if not settings.S3_BUCKET_NAME:
        raise ImproperlyConfigured('S3_BUCKET_NAME is required.')


def get_s3_client():
    _require_boto3()
    _require_s3_config()

    kwargs = {
        'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
        'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY,
        'region_name': settings.S3_REGION_NAME,
    }

    if settings.S3_ENDPOINT_URL:
        kwargs['endpoint_url'] = settings.S3_ENDPOINT_URL

    return boto3.client('s3', **kwargs)


def ensure_bucket_exists():
    client = get_s3_client()
    bucket = settings.S3_BUCKET_NAME

    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        create_kwargs = {'Bucket': bucket}
        if settings.S3_REGION_NAME and settings.S3_REGION_NAME != 'us-east-1':
            create_kwargs['CreateBucketConfiguration'] = {'LocationConstraint': settings.S3_REGION_NAME}
        client.create_bucket(**create_kwargs)

    try:
        client.put_public_access_block(
            Bucket=bucket,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': True,
                'IgnorePublicAcls': True,
                'BlockPublicPolicy': True,
                'RestrictPublicBuckets': True,
            },
        )
    except ClientError as exc:
        error_code = exc.response.get('Error', {}).get('Code', '')

        # Some S3-compatible providers (e.g. MinIO) do not fully support this API.
        # The bucket is still private because uploads use ACL=private and access is
        # provided only via authenticated app APIs + presigned URLs.
        if error_code in {'MalformedXML', 'NotImplemented', 'InvalidRequest'}:
            return
        raise


def _build_s3_key(original_name, owner_id):
    safe_name = os.path.basename(original_name)
    date_prefix = datetime.utcnow().strftime('%Y/%m/%d')
    random_part = uuid.uuid4().hex
    return f"secure-files/{owner_id}/{date_prefix}/{random_part}-{safe_name}"


def upload_file(uploaded, owner):
    client = get_s3_client()
    key = _build_s3_key(uploaded.name, owner.id)

    extra_args = {'ACL': 'private'}
    if getattr(uploaded, 'content_type', None):
        extra_args['ContentType'] = uploaded.content_type

    client.upload_fileobj(
        Fileobj=uploaded,
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        ExtraArgs=extra_args,
    )

    return SecureFile.objects.create(
        owner=owner,
        original_name=uploaded.name,
        s3_key=key,
        content_type=getattr(uploaded, 'content_type', '') or '',
        size=getattr(uploaded, 'size', 0) or 0,
    )


def generate_download_url(s3_key):
    client = get_s3_client()
    return client.generate_presigned_url(
        ClientMethod='get_object',
        Params={
            'Bucket': settings.S3_BUCKET_NAME,
            'Key': s3_key,
        },
        ExpiresIn=settings.S3_PRESIGNED_URL_EXPIRY,
    )


def delete_file(s3_key):
    client = get_s3_client()
    client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)


def download_file_bytes(s3_key):
    client = get_s3_client()
    response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    body = response['Body'].read()
    content_type = response.get('ContentType') or 'application/octet-stream'
    return body, content_type
