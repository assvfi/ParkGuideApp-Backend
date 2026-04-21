from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import AccountApplication, PasskeyCredential, TwoFactorAuth
from .services import upload_application_cv


User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password']

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user


class AccountApplicationSerializer(serializers.ModelSerializer):
    cv_file = serializers.FileField(write_only=True)

    class Meta:
        model = AccountApplication
        fields = [
            'id',
            'full_name',
            'email',
            'phone_number',
            'birthdate',
            'cv_file',
            'cv_original_name',
            'cv_size',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'cv_original_name', 'cv_size']

    def validate_full_name(self, value):
        cleaned = (value or '').strip()
        if len(cleaned) < 3:
            raise serializers.ValidationError('Please provide your full name.')
        return cleaned

    def validate_phone_number(self, value):
        cleaned = (value or '').strip().replace(' ', '').replace('-', '')
        if cleaned.startswith('0'):
            cleaned = f'+60{cleaned[1:]}'
        elif not cleaned.startswith('+60'):
            cleaned = f'+60{cleaned}'
        return cleaned

    def validate_email(self, value):
        return (value or '').strip().lower()

    def validate(self, attrs):
        email = attrs.get('email')
        pending_exists = AccountApplication.objects.filter(
            email=email,
            status=AccountApplication.STATUS_PENDING,
        ).exists()
        if pending_exists:
            raise serializers.ValidationError({'email': 'You already have a pending application.'})

        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({'email': 'An account with this email already exists.'})

        return attrs

    def create(self, validated_data):
        uploaded_cv = validated_data.pop('cv_file')
        email = validated_data.get('email', '')
        uploaded = upload_application_cv(uploaded_cv, applicant_email=email)
        validated_data.update(
            {
                'cv_storage_key': uploaded['storage_key'],
                'cv_original_name': uploaded['original_name'],
                'cv_content_type': uploaded['content_type'],
                'cv_size': uploaded['size'],
            }
        )
        return super().create(validated_data)


class PasskeyCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = PasskeyCredential
        fields = [
            'id',
            'label',
            'credential_device_type',
            'credential_backed_up',
            'transports',
            'last_used_at',
            'created_at',
        ]


class TwoFactorAuthSerializer(serializers.ModelSerializer):
    class Meta:
        model = TwoFactorAuth
        fields = [
            'is_enabled',
            'confirmed_at',
            'updated_at',
        ]
